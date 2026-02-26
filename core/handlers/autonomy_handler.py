class AutonomyHandler:
    @staticmethod
    def handle(event, context):
        Action = context["Action"]
        action_planner = context["engines"]["action_planner"]
        confirmation_queue = context["stores"]["confirmation_queue"]

        if event.type == "ActionApproved":
            plan = action_planner.plan(event.payload)
            return [Action(type="ActionPlanGenerated", payload=plan)]

        if event.type == "ActionPlanGenerated":
            plan_id = confirmation_queue.add(event.payload)
            return [
                Action(
                    type="AwaitingConfirmation",
                    payload={"plan_id": plan_id, "plan": event.payload},
                )
            ]

        if event.type == "ListPendingConfirmations":
            pending = confirmation_queue.list_pending()
            return [Action(type="PendingConfirmationsListed", payload={"items": pending})]

        if event.type == "ConfirmAction":
            plan_id = str(event.payload.get("plan_id", ""))
            approved = confirmation_queue.approve(plan_id)
            if approved is None:
                return []
            return [
                Action(
                    type="ActionConfirmed",
                    payload={"plan_id": approved["id"], "plan": approved["plan"]},
                )
            ]

        if event.type == "RejectAction":
            plan_id = str(event.payload.get("plan_id", ""))
            rejected = confirmation_queue.reject(plan_id)
            if rejected is None:
                return []
            return [
                Action(
                    type="ActionRejected",
                    payload={"plan_id": rejected["id"], "plan": rejected["plan"]},
                )
            ]

        return []


def handle(event, context):
    return AutonomyHandler.handle(event, context)
