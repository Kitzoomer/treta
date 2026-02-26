import logging
from datetime import datetime

from core.domain.lifecycle import EXECUTION_STATUSES


logger = logging.getLogger("treta.control")


class OpportunityHandler:
    @staticmethod
    def handle(event, context):
        Action = context["Action"]
        control = context["control"]

        stores = context["stores"]
        engines = context["engines"]

        opportunity_store = stores["opportunity_store"]
        product_proposal_store = stores["product_proposal_store"]
        product_launch_store = stores["product_launch_store"]
        product_plan_store = stores["product_plan_store"]
        revenue_attribution_store = stores["revenue_attribution_store"]
        subreddit_performance_store = stores["subreddit_performance_store"]

        alignment_engine = engines["alignment_engine"]
        product_engine = engines["product_engine"]
        product_builder = engines["product_builder"]
        execution_engine = engines["execution_engine"]

        if event.type == "OpportunityDetected":
            created = opportunity_store.add(
                item_id=str(event.payload.get("id", "")).strip() or None,
                source=str(event.payload.get("source", "unknown")),
                title=str(event.payload.get("title", "")),
                summary=str(event.payload.get("summary", event.payload.get("snippet", ""))),
                opportunity=dict(event.payload.get("opportunity", {})),
            )

            if created.get("source") == "reddit_public" and control.has_active_proposal():
                return []

            alignment = alignment_engine.evaluate(
                created,
                {
                    "recent_proposals": product_proposal_store.list()[:5],
                },
            )
            if not alignment["aligned"]:
                opportunity_store.set_status(created["id"], "strategically_filtered")
                return []

            proposal = product_engine.generate(created)
            subreddit = str(event.payload.get("subreddit", "")).strip() or "unknown"
            proposal["alignment_score"] = alignment["alignment_score"]
            proposal["alignment_reason"] = alignment["reason"]
            product_proposal_store.add(proposal)
            subreddit_performance_store.record_proposal_generated(subreddit)
            return [
                Action(
                    type="ProductProposalGenerated",
                    payload={"proposal_id": proposal["id"], "proposal": proposal},
                )
            ]

        if event.type == "ListProductProposals":
            items = product_proposal_store.list()
            return [Action(type="ProductProposalsListed", payload={"items": items})]

        if event.type == "GetProductProposalById":
            proposal_id = str(event.payload.get("id", ""))
            item = product_proposal_store.get(proposal_id)
            if item is None:
                return []
            return [Action(type="ProductProposalFetched", payload={"item": item})]

        proposal_transitions = {
            "ApproveProposal": "approved",
            "RejectProposal": "rejected",
            "StartBuildingProposal": "building",
            "MarkReadyToLaunch": "ready_to_launch",
            "MarkProposalLaunched": "launched",
            "ArchiveProposal": "archived",
        }
        if event.type in proposal_transitions:
            proposal_id = str(event.payload.get("proposal_id", "")).strip()
            if not proposal_id:
                return []
            next_status = proposal_transitions[event.type]
            proposal = product_proposal_store.get(proposal_id)
            if proposal is None:
                return []
            proposals = product_proposal_store.list()
            control.domain_integrity_policy.validate_transition(proposal, next_status, proposals)
            updated = product_proposal_store.transition_status(
                proposal_id=proposal_id,
                new_status=next_status,
            )
            control._validate_global()
            if updated["status"] in EXECUTION_STATUSES:
                control._refresh_execution_focus()
                updated = product_proposal_store.get(updated["id"]) or updated
            actions = [
                Action(
                    type="ProductProposalStatusChanged",
                    payload={"proposal_id": updated["id"], "status": updated["status"], "proposal": updated},
                )
            ]
            if event.type == "MarkProposalLaunched":
                launch = product_launch_store.add_from_proposal(updated["id"])
                launch = product_launch_store.mark_launched(launch["id"])
                control._validate_global()
                control._refresh_execution_focus()
                launch = product_launch_store.get(launch["id"]) or launch
                actions.append(
                    Action(
                        type="ProductLaunched",
                        payload={
                            "launch_id": launch["id"],
                            "proposal_id": updated["id"],
                        },
                    )
                )
            return actions

        if event.type == "ListProductLaunchesRequested":
            items = product_launch_store.list()
            return [Action(type="ProductLaunchesListed", payload={"items": items})]

        if event.type == "GetProductLaunchRequested":
            launch_id = str(event.payload.get("launch_id", "")).strip()
            launch = product_launch_store.get(launch_id)
            if launch is None:
                return []
            return [Action(type="ProductLaunchReturned", payload={"launch": launch})]

        if event.type == "AddProductLaunchSale":
            launch_id = str(event.payload.get("launch_id", "")).strip()
            amount = float(event.payload.get("amount", 0))
            updated = product_launch_store.add_sale(launch_id, amount)
            return [Action(type="ProductLaunchUpdated", payload={"launch": updated})]

        if event.type == "TransitionProductLaunchStatus":
            launch_id = str(event.payload.get("launch_id", "")).strip()
            status = str(event.payload.get("status", "")).strip()
            updated = product_launch_store.transition_status(launch_id, status)
            control._validate_global()
            return [Action(type="ProductLaunchUpdated", payload={"launch": updated})]

        if event.type == "BuildProductPlanRequested":
            proposal_id = str(event.payload.get("proposal_id", ""))
            proposal = product_proposal_store.get(proposal_id)
            if proposal is None:
                return []

            if str(proposal.get("status", "")).strip() == "draft" and str(proposal.get("source_opportunity_id", "")).strip():
                proposals = product_proposal_store.list()
                control.domain_integrity_policy.validate_transition(proposal, "approved", proposals)
                proposal = product_proposal_store.transition_status(
                    proposal_id=proposal_id,
                    new_status="approved",
                )
                control._validate_global()

            control.domain_integrity_policy.validate_plan_build_precondition(proposal)

            existing = product_plan_store.get_by_proposal_id(proposal_id)
            if existing is not None:
                return [
                    Action(
                        type="ProductPlanBuilt",
                        payload={
                            "plan_id": existing["plan_id"],
                            "proposal_id": proposal_id,
                            "plan": existing,
                        },
                    )
                ]

            plan = product_builder.build(proposal)
            stored = product_plan_store.add(plan)
            control._validate_global()
            return [
                Action(
                    type="ProductPlanBuilt",
                    payload={
                        "plan_id": stored["plan_id"],
                        "proposal_id": stored["proposal_id"],
                        "plan": stored,
                    },
                )
            ]

        if event.type == "ListProductPlansRequested":
            items = product_plan_store.list()
            return [Action(type="ProductPlansListed", payload={"items": items})]

        if event.type == "GetProductPlanRequested":
            plan_id = str(event.payload.get("plan_id", ""))
            plan = product_plan_store.get(plan_id)
            if plan is None:
                return []
            return [Action(type="ProductPlanReturned", payload={"plan": plan})]

        if event.type == "ExecuteProductPlanRequested":
            proposal_id = str(event.payload.get("proposal_id", ""))
            proposal = product_proposal_store.get(proposal_id)
            if proposal is None:
                return []

            execution_package = execution_engine.generate_execution_package(proposal)
            tracking_id = f"treta-{proposal_id[:6]}-{int(datetime.utcnow().timestamp())}"
            reddit_post = execution_package.get("reddit_post")
            if isinstance(reddit_post, dict):
                reddit_post["body"] = f"{str(reddit_post.get('body', '')).rstrip()}\n\nTracking: {tracking_id}"
            execution_package["gumroad_description"] = (
                f"{str(execution_package.get('gumroad_description', '')).rstrip()}\n\nTracking: {tracking_id}"
            )
            execution_package["short_pitch"] = (
                f"{str(execution_package.get('short_pitch', '')).rstrip()} (Tracking: {tracking_id})"
            )

            source_opportunity_id = str(proposal.get("source_opportunity_id", "")).strip()
            subreddit = None
            if source_opportunity_id:
                opportunity = opportunity_store.get(source_opportunity_id)
                if opportunity is not None:
                    subreddit = opportunity.get("subreddit") or opportunity.get("opportunity", {}).get("subreddit")

            revenue_attribution_store.upsert_tracking(
                tracking_id=tracking_id,
                proposal_id=proposal_id,
                product_id=proposal_id,
                subreddit=str(subreddit).strip() if subreddit else None,
                post_id=str(source_opportunity_id).strip() if source_opportunity_id else None,
                price=proposal.get("price_suggestion"),
                created_at=datetime.utcnow().isoformat() + "Z",
            )
            if subreddit:
                subreddit_performance_store.record_plan_executed(str(subreddit).strip())
            logger.info(f"[EXECUTION] proposal_id={proposal_id}")
            actions = [
                Action(
                    type="ProductPlanExecuted",
                    payload={
                        "proposal_id": proposal_id,
                        "execution_package": execution_package,
                        "tracking_id": tracking_id,
                    },
                )
            ]

            proposals = product_proposal_store.list()
            control.domain_integrity_policy.validate_transition(proposal, "ready_for_review", proposals)
            updated = product_proposal_store.transition_status(
                proposal_id=proposal_id,
                new_status="ready_for_review",
            )
            control._validate_global()
            actions.append(
                Action(
                    type="ProductProposalStatusChanged",
                    payload={"proposal_id": updated["id"], "status": updated["status"], "proposal": updated},
                )
            )
            return actions

        if event.type == "ListOpportunities":
            status = event.payload.get("status")
            items = opportunity_store.list(status=str(status) if status else None)
            return [Action(type="OpportunitiesListed", payload={"items": items})]

        if event.type == "EvaluateOpportunityById":
            item_id = str(event.payload.get("id", ""))
            target = opportunity_store.get(item_id)
            if target is None:
                return []

            result = control.evaluate_opportunity(
                target["opportunity"],
                request_id=event.request_id or str(event.payload.get("request_id", "") or ""),
                trace_id=event.trace_id or str(event.payload.get("trace_id", "") or ""),
                event_id=event.event_id,
            )
            updated = opportunity_store.set_decision(item_id, result)
            if updated is None:
                return []

            return [
                Action(
                    type="OpportunityEvaluated",
                    payload={"id": item_id, "decision": result, "item": updated},
                )
            ]

        if event.type == "OpportunityDismissed":
            item_id = str(event.payload.get("id", ""))
            updated = opportunity_store.set_status(item_id, "dismissed")
            if updated is None:
                return []
            return []

        return []


def handle(event, context):
    return OpportunityHandler.handle(event, context)
