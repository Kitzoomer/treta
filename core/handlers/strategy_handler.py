from datetime import datetime, timedelta, timezone
import logging

from core.config import ACTION_EXECUTION_TIMEOUT_SECONDS, STRATEGY_DECISION_COOLDOWN_MINUTES

logger = logging.getLogger("treta.control")


class StrategyHandler:
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

        latest_execution = execution_store.latest_for_action(action_id)
        if isinstance(latest_execution, dict):
            latest_status = str(latest_execution.get("status") or "")
            latest_execution_id = latest_execution.get("id")
            if latest_status == "success":
                logger.info("Strategy action execution skipped: already successful", extra={"action_id": action_id})
                return [Action(type="StrategyActionExecutionSkipped", payload={"action_id": action_id, "reason": "already_success"})]
            if latest_status == "running":
                started_at = StrategyHandler._parse_iso_datetime(latest_execution.get("started_at"))
                now = datetime.now(timezone.utc)
                if started_at is not None and (now - started_at).total_seconds() < ACTION_EXECUTION_TIMEOUT_SECONDS:
                    logger.warning(
                        "Strategy action execution already in progress",
                        extra={"action_id": action_id, "execution_id": latest_execution_id},
                    )
                    return [
                        Action(
                            type="StrategyActionExecutionSkipped",
                            payload={"action_id": action_id, "reason": "execution_already_in_progress"},
                        )
                    ]
                if latest_execution_id is not None:
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
        execution_id = execution_store.create_queued(
            action_id=action_id,
            action_type=str(action.get("type") or ""),
            executor=executor_name,
            context=ctx,
        )
        execution_store.mark_running(execution_id)

        if executor is None:
            execution_store.complete(execution_id, status="skipped", output_payload={"reason": "no_executor"})
            return [Action(type="StrategyActionExecutionSkipped", payload={"action_id": action_id, "reason": "no_executor"})]

        try:
            output = executor.execute(action, ctx)
            execution_store.complete(execution_id, status="success", output_payload=output)
            target_status = "auto_executed" if str(ctx.get("strategy_status")) == "auto_executed" else "executed"
            updated = action_store.set_status(action_id, target_status)
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

        return []


def handle(event, context):
    return StrategyHandler.handle(event, context)
