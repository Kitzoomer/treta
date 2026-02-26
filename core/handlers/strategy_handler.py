from datetime import datetime, timedelta, timezone
import logging

from core.config import STRATEGY_DECISION_COOLDOWN_MINUTES

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
