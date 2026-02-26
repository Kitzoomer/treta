import logging

logger = logging.getLogger("treta.control")


class StrategyHandler:
    @staticmethod
    def handle(event, context):
        Action = context["Action"]
        control = context["control"]
        strategy_decision_engine = context["engines"]["strategy_decision_engine"]

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

            result = strategy_decision_engine.decide(
                request_id=event.request_id or str(event.payload.get("request_id", "") or ""),
                trace_id=event.trace_id or str(event.payload.get("trace_id", "") or ""),
                event_id=event.event_id,
            )
            return [Action(type="StrategyDecisionCompleted", payload=result)]

        return []


def handle(event, context):
    return StrategyHandler.handle(event, context)
