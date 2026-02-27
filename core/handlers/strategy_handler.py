from datetime import datetime, timedelta, timezone
import logging

from core.config import (
    ACTION_APPROVAL_MIN_RISK_LEVEL,
    ACTION_CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    ACTION_CIRCUIT_BREAKER_WINDOW_SECONDS,
    ACTION_EXECUTION_TIMEOUT_SECONDS,
    STRATEGY_DECISION_COOLDOWN_MINUTES,
)

logger = logging.getLogger("treta.control")


class StrategyHandler:
    _TERMINAL_ACTION_STATUSES = {"completed", "failed", "rejected"}
    _RISK_LEVEL_ORDER = {"low": 1, "medium": 2, "high": 3}

    @staticmethod
    def _parse_iso_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _risk_level_value(level: str | None) -> int:
        return StrategyHandler._RISK_LEVEL_ORDER.get(str(level or "").strip().lower(), 0)

    @staticmethod
    def _is_approval_required(action: dict) -> bool:
        action_risk = StrategyHandler._risk_level_value(action.get("risk_level"))
        required_risk = StrategyHandler._risk_level_value(ACTION_APPROVAL_MIN_RISK_LEVEL)
        if required_risk <= 0:
            return False
        return action_risk >= required_risk

    @staticmethod
    def _is_action_approved(action: dict, event_payload: dict) -> bool:
        payload_flag = event_payload.get("approved")
        if payload_flag is not None:
            return bool(payload_flag)
        strategy_status = str(event_payload.get("strategy_status") or "").strip().lower()
        if strategy_status == "auto_executed":
            return True
        status = str(action.get("status") or "").strip().lower()
        if status in {"auto_executed", "approved"}:
            return True
        return str(action.get("approved_by") or "").strip() != ""

    @staticmethod
    def _has_minimum_action_payload(action: dict) -> bool:
        required_keys = ("id", "type", "target_id", "reasoning", "status")
        for key in required_keys:
            if not str(action.get(key) or "").strip():
                return False
        return True

    @staticmethod
    def _should_open_circuit_breaker(execution_store, action_id: str) -> bool:
        recent = execution_store.list_for_action(action_id, limit=max(5, ACTION_CIRCUIT_BREAKER_FAILURE_THRESHOLD * 3))
        if not recent:
            return False
        now = datetime.now(timezone.utc)
        failures = 0
        for item in recent:
            status = str(item.get("status") or "").strip().lower()
            if status not in {"failed", "failed_timeout"}:
                continue
            finished_at = StrategyHandler._parse_iso_datetime(item.get("finished_at"))
            if finished_at is None:
                continue
            age_seconds = (now - finished_at).total_seconds()
            if age_seconds < 0 or age_seconds > ACTION_CIRCUIT_BREAKER_WINDOW_SECONDS:
                continue
            failures += 1
            if failures >= ACTION_CIRCUIT_BREAKER_FAILURE_THRESHOLD:
                return True
        return False

    @staticmethod
    def _post_verify_executor_output(output: dict) -> tuple[bool, str]:
        status = str(output.get("status") or "").strip().lower()
        if status in {"failed", "error"}:
            return False, "executor_reported_failure"
        if not output:
            return False, "output_empty_or_incoherent"
        if status and status not in {"success", "ok", "queued", "done"}:
            return False, "output_empty_or_incoherent"
        return True, ""

    @staticmethod
    def _log_execution_result(action: dict, executor_name: str, start_time: datetime, result: str) -> None:
        duration_ms = max(0, int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000))
        logger.info(
            "Strategy action execution result",
            extra={
                "action_id": str(action.get("id") or ""),
                "decision_id": str(action.get("decision_id") or ""),
                "executor_name": executor_name,
                "duration_ms": duration_ms,
                "result": result,
            },
        )

    @staticmethod
    def _cooldown_status(storage, now: datetime) -> tuple[bool, float]:
        if storage is None:
            return False, 0.0
        last_strategy_log = storage.get_latest_decision_log_by_type("strategy_action")
        if not isinstance(last_strategy_log, dict):
            return False, 0.0
        created_at = StrategyHandler._parse_iso_datetime(last_strategy_log.get("created_at"))
        if created_at is None:
            return False, 0.0
        cooldown_until = created_at + timedelta(minutes=STRATEGY_DECISION_COOLDOWN_MINUTES)
        remaining_seconds = (cooldown_until - now).total_seconds()
        if remaining_seconds <= 0:
            return False, 0.0
        return True, remaining_seconds / 60.0

    @staticmethod
    def _execute_strategy_action(event, context):
        Action = context["Action"]
        layer = context.get("strategy_action_execution_layer")
        if layer is None:
            return []
        action_store = layer._strategy_action_store
        execution_store = layer._action_execution_store
        registry = layer._executor_registry
        storage = context.get("storage")

        action_id = str(event.payload.get("action_id") or "").strip()
        if not action_id:
            return []
        action = action_store.get(action_id)
        if action is None:
            return []

        if execution_store is None or registry is None:
            return []

        decision_id = str(action.get("decision_id") or "")

        def _log_failed_strategy_action(updated_action: dict, reason: str, error_text: str) -> None:
            if storage is None:
                return
            storage.create_decision_log(
                {
                    "decision_type": "strategy_action",
                    "entity_type": "action",
                    "entity_id": str(updated_action.get("id") or action_id),
                    "action_type": "execute",
                    "decision": "ALLOW",
                    "inputs_json": {
                        "action_id": action_id,
                        "requested_status": str(event.payload.get("strategy_status") or "executed"),
                    },
                    "outputs_json": {"action": updated_action},
                    "reason": reason,
                    "status": "failed",
                    "error": error_text,
                    "correlation_id": str(ctx.get("correlation_id") or ""),
                    "request_id": str(ctx.get("request_id") or ""),
                    "trace_id": str(ctx.get("trace_id") or ""),
                    "event_id": event.event_id,
                }
            )

        if not StrategyHandler._has_minimum_action_payload(action):
            logger.warning("Strategy action execution skipped: invalid payload", extra={"action_id": action_id, "decision_id": decision_id})
            return [Action(type="StrategyActionExecutionSkipped", payload={"action_id": action_id, "reason": "invalid_payload"})]

        current_status = str(action.get("status") or "").strip().lower()
        if current_status in StrategyHandler._TERMINAL_ACTION_STATUSES:
            logger.info("Strategy action execution skipped: terminal status", extra={"action_id": action_id, "decision_id": decision_id, "status": current_status})
            return [Action(type="StrategyActionExecutionSkipped", payload={"action_id": action_id, "reason": "terminal_status"})]

        if StrategyHandler._is_approval_required(action) and not StrategyHandler._is_action_approved(action, event.payload):
            logger.info("Strategy action execution skipped: approval required", extra={"action_id": action_id, "decision_id": decision_id, "risk_level": action.get("risk_level")})
            return [Action(type="StrategyActionExecutionSkipped", payload={"action_id": action_id, "reason": "approval_required"})]

        if StrategyHandler._should_open_circuit_breaker(execution_store, action_id):
            logger.warning("Strategy action execution skipped: circuit breaker open", extra={"action_id": action_id, "decision_id": decision_id})
            return [Action(type="StrategyActionExecutionSkipped", payload={"action_id": action_id, "reason": "circuit_breaker_open"})]

        latest_execution = execution_store.latest_for_action(action_id)
        if isinstance(latest_execution, dict):
            latest_status = str(latest_execution.get("status") or "").strip().lower()
            latest_execution_id = latest_execution.get("id")
            if latest_status == "success":
                logger.info("Strategy action execution skipped: already successful", extra={"action_id": action_id, "decision_id": decision_id})
                return [Action(type="StrategyActionExecutionSkipped", payload={"action_id": action_id, "reason": "already_success"})]
            if latest_status == "running":
                started_at = StrategyHandler._parse_iso_datetime(latest_execution.get("started_at"))
                now = datetime.now(timezone.utc)
                if started_at is not None and (now - started_at).total_seconds() >= ACTION_EXECUTION_TIMEOUT_SECONDS and latest_execution_id is not None:
                    execution_store.mark_failed_timeout(
                        int(latest_execution_id),
                        error="execution timeout exceeded before completion",
                    )

        ctx = {
            "request_id": event.request_id or str(event.payload.get("request_id") or ""),
            "trace_id": event.trace_id or str(event.payload.get("trace_id") or ""),
            "correlation_id": str(event.payload.get("correlation_id") or action.get("decision_id") or ""),
            "strategy_status": str(event.payload.get("strategy_status") or ""),
            "prompt": str(action.get("reasoning") or ""),
        }

        executor = registry.get_executor_for(str(action.get("type") or ""))
        executor_name = executor.name if executor is not None else "none"
        started = execution_store.try_start_execution(
            action_id=action_id,
            decision_id=decision_id,
            executor_name=executor_name,
            action_type=str(action.get("type") or ""),
            context=ctx,
        )
        if not started:
            logger.warning("Strategy action execution skipped: already running", extra={"action_id": action_id, "decision_id": decision_id})
            return [Action(type="StrategyActionExecutionSkipped", payload={"action_id": action_id, "reason": "already_running"})]
        started_execution = execution_store.latest_for_action(action_id)
        execution_id = int((started_execution or {}).get("id") or 0)
        if execution_id <= 0:
            logger.error("Strategy action execution start failed: missing execution id", extra={"action_id": action_id, "decision_id": decision_id})
            return [Action(type="StrategyActionExecutionSkipped", payload={"action_id": action_id, "reason": "execution_start_failed"})]
        started_at = datetime.now(timezone.utc)

        if executor is None:
            execution_store.complete(execution_id, status="skipped", output_payload={"reason": "no_executor"})
            StrategyHandler._log_execution_result(action, executor_name, started_at, "skipped")
            return [Action(type="StrategyActionExecutionSkipped", payload={"action_id": action_id, "reason": "no_executor"})]

        try:
            output = executor.execute(action, ctx)
            if str(output.get("status") or "").lower() == "failed":
                error_text = str(output.get("error") or "executor_reported_failure")
                execution_store.complete(execution_id, status="failed", error=error_text, output_payload=output)
                updated = action_store.set_status(action_id, "failed")
                StrategyHandler._log_execution_result(action, executor_name, started_at, "failed")
                _log_failed_strategy_action(
                    updated_action=updated,
                    reason="Strategy action execution failed.",
                    error_text=error_text,
                )
                if storage is not None:
                    storage.conn.execute(
                        """
                        INSERT OR REPLACE INTO decision_outcomes (
                            decision_id, strategy_type, was_autonomous, predicted_risk,
                            revenue_generated, outcome, evaluated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(updated.get("decision_id") or f"action_execution:{action_id}"),
                            str(updated.get("type") or ""),
                            0,
                            float(updated.get("risk_score", 0) or 0),
                            float(updated.get("revenue_generated", updated.get("revenue_delta", 0)) or 0),
                            "failed",
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )
                    storage.conn.commit()
                return [
                    Action(
                        type="StrategyActionFailed",
                        payload={
                            "action_id": action_id,
                            "status": "failed",
                            "executor": executor_name,
                            "correlation_id": str(ctx.get("correlation_id") or ""),
                            "action": updated,
                            "error": error_text,
                            "execution_id": execution_id,
                            "output": output,
                        },
                    )
                ]

            post_verify_ok, post_verify_reason = StrategyHandler._post_verify_executor_output(output)
            if not post_verify_ok:
                execution_store.complete(execution_id, status="failed", error="post_verify_failed", output_payload=output)
                updated = action_store.set_status(action_id, "failed")
                StrategyHandler._log_execution_result(action, executor_name, started_at, "post_verify_failed")
                _log_failed_strategy_action(
                    updated_action=updated,
                    reason="Strategy action execution failed post verification.",
                    error_text="post_verify_failed",
                )
                return [
                    Action(
                        type="StrategyActionFailed",
                        payload={
                            "action_id": action_id,
                            "status": "failed",
                            "executor": executor_name,
                            "correlation_id": str(ctx.get("correlation_id") or ""),
                            "action": updated,
                            "error": "post_verify_failed",
                            "verification_reason": post_verify_reason,
                            "execution_id": execution_id,
                            "output": output,
                        },
                    )
                ]

            execution_store.complete(execution_id, status="success", output_payload=output)
            target_status = "auto_executed" if str(ctx.get("strategy_status")) == "auto_executed" else "executed"
            updated = action_store.set_status(action_id, target_status)
            StrategyHandler._log_execution_result(action, executor_name, started_at, "success")
            if storage is not None:
                storage.conn.execute(
                    """
                    INSERT OR REPLACE INTO decision_outcomes (
                        decision_id, strategy_type, was_autonomous, predicted_risk,
                        revenue_generated, outcome, evaluated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(updated.get("decision_id") or f"action_execution:{action_id}"),
                        str(updated.get("type") or ""),
                        1 if target_status == "auto_executed" else 0,
                        float(updated.get("risk_score", 0) or 0),
                        float(updated.get("revenue_generated", updated.get("revenue_delta", 0)) or 0),
                        "success",
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                storage.conn.commit()
            return [
                Action(
                    type="StrategyActionExecuted",
                    payload={
                        "action_id": action_id,
                        "status": "success",
                        "executor": executor_name,
                        "correlation_id": str(ctx.get("correlation_id") or ""),
                        "action": updated,
                        "execution_id": execution_id,
                        "output": output,
                    },
                )
            ]
        except Exception as exc:
            execution_store.complete(execution_id, status="failed", error=str(exc), output_payload={})
            updated = action_store.set_status(action_id, "failed")
            StrategyHandler._log_execution_result(action, executor_name, started_at, "failed_exception")
            _log_failed_strategy_action(
                updated_action=updated,
                reason="Strategy action execution failed with exception.",
                error_text=str(exc),
            )
            if storage is not None:
                storage.conn.execute(
                    """
                    INSERT OR REPLACE INTO decision_outcomes (
                        decision_id, strategy_type, was_autonomous, predicted_risk,
                        revenue_generated, outcome, evaluated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(updated.get("decision_id") or f"action_execution:{action_id}"),
                        str(updated.get("type") or ""),
                        0,
                        float(updated.get("risk_score", 0) or 0),
                        float(updated.get("revenue_generated", updated.get("revenue_delta", 0)) or 0),
                        "failed",
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                storage.conn.commit()
            return [
                Action(
                    type="StrategyActionFailed",
                    payload={
                        "action_id": action_id,
                        "status": "failed",
                        "executor": executor_name,
                        "correlation_id": str(ctx.get("correlation_id") or ""),
                        "action": updated,
                        "error": str(exc),
                        "execution_id": execution_id,
                    },
                )
            ]

    @staticmethod
    def handle(event, context):
        Action = context["Action"]
        control = context["control"]
        strategy_decision_engine = context["engines"]["strategy_decision_engine"]
        storage = context.get("storage")

        if event.type == "EvaluateOpportunity":
            result = control.evaluate_opportunity(
                event.payload,
                request_id=event.request_id or str(event.payload.get("request_id", "") or ""),
                trace_id=event.trace_id or str(event.payload.get("trace_id", "") or ""),
                event_id=event.event_id,
            )
            logger.info(f"[DECISION] score={result['score']:.2f} decision={result['decision']}")
            return [Action(type="OpportunityEvaluated", payload=result)]

        if event.type == "ExecuteStrategyAction":
            return StrategyHandler._execute_strategy_action(event, context)

        if event.type == "RunStrategyDecision":
            if strategy_decision_engine is None:
                logger.warning("RunStrategyDecision received without strategy_decision_engine configured")
                return []

            request_id = event.request_id or str(event.payload.get("request_id", "") or "")
            trace_id = event.trace_id or str(event.payload.get("trace_id", "") or "")
            now = datetime.now(timezone.utc)
            cooldown_active, remaining_minutes = StrategyHandler._cooldown_status(storage=storage, now=now)
            if cooldown_active:
                logger.info(
                    "Strategy decision skipped due to active cooldown",
                    extra={
                        "request_id": request_id,
                        "trace_id": trace_id,
                        "event_id": event.event_id,
                        "cooldown_remaining_minutes": round(remaining_minutes, 2),
                    },
                )
                if storage is not None:
                    storage.create_decision_log(
                        {
                            "decision_type": "strategy_action_skipped",
                            "entity_type": "portfolio",
                            "entity_id": "global",
                            "action_type": "recommend",
                            "decision": "SKIPPED",
                            "policy_name": "StrategyDecisionCooldown",
                            "reason": "cooldown_active",
                            "correlation_id": request_id,
                            "request_id": request_id,
                            "trace_id": trace_id,
                            "event_id": event.event_id,
                            "status": "skipped",
                            "outputs_json": {
                                "cooldown_remaining_minutes": round(remaining_minutes, 2),
                                "cooldown_minutes": STRATEGY_DECISION_COOLDOWN_MINUTES,
                            },
                        }
                    )
                return [
                    Action(
                        type="StrategyDecisionCompleted",
                        payload={
                            "status": "skipped",
                            "reason": "cooldown_active",
                            "cooldown_active": True,
                            "cooldown_remaining_minutes": round(remaining_minutes, 2),
                        },
                    )
                ]

            result = strategy_decision_engine.decide(
                request_id=request_id,
                trace_id=trace_id,
                event_id=event.event_id,
            )
            payload = dict(result)
            payload["status"] = "executed"
            payload["cooldown_active"] = False
            return [Action(type="StrategyDecisionCompleted", payload=payload)]

        if event.type == "OpportunityEvaluated":
            now = datetime.now(timezone.utc)
            in_cooldown, cooldown_remaining_minutes = StrategyHandler._cooldown_status(storage, now)
            decision = strategy_decision_engine.make_decision(event.payload)
            if in_cooldown and decision.get("type") == "strategy_action":
                logger.info(
                    "[STRATEGY] cooldown_active skip decision",
                    extra={"cooldown_remaining_minutes": round(cooldown_remaining_minutes, 2)},
                )
                return [
                    Action(
                        type="NoActionTaken",
                        payload={
                            **decision,
                            "decision": "wait",
                            "reason": "cooldown_active",
                            "cooldown_remaining_minutes": round(cooldown_remaining_minutes, 2),
                        },
                    )
                ]
            if decision.get("type") == "strategy_action":
                if storage is not None:
                    try:
                        storage.log_decision_event(
                            event_type="strategy_action",
                            payload={
                                "reason": str(decision.get("reason", "")),
                                "action_type": str(decision.get("action_type", "")),
                                "target_id": str(decision.get("target_id", "")),
                                "confidence": float(decision.get("confidence", 0.0) or 0.0),
                                "timestamp": now.isoformat(),
                            },
                            confidence=float(decision.get("confidence", 0.0) or 0.0),
                            risk_level=str(decision.get("action_type", "")),
                        )
                    except Exception as exc:  # pragma: no cover - defensive logging
                        logger.warning("Failed to log strategy decision event", extra={"error": str(exc)})
                return [Action(type="ProposeStrategyAction", payload=decision)]
            return [Action(type="NoActionTaken", payload=decision)]

        return []
