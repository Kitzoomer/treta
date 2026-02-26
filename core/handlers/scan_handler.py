import logging

logger = logging.getLogger("treta.control")


class ScanHandler:
    @staticmethod
    def handle(event, context):
        Action = context["Action"]
        control = context["control"]

        if event.type == "DailyBriefRequested":
            logger.info("[CONTROL] DailyBriefRequested -> would build daily brief summary (stub)")
            return [Action(type="BuildDailyBrief", payload={"dry_run": True})]

        if event.type == "OpportunityScanRequested":
            logger.info("[CONTROL] OpportunityScanRequested -> would run opportunity scan (stub)")
            return [Action(type="RunOpportunityScan", payload={"dry_run": True})]

        if event.type == "RunInfoproductScan":
            control._scan_reddit_public_opportunities()
            control._generate_reddit_daily_plan()
            return []

        if event.type == "EmailTriageRequested":
            logger.info("[CONTROL] EmailTriageRequested -> would triage inbox in dry-run mode (stub)")
            return [Action(type="RunEmailTriage", payload={"dry_run": True})]

        if event.type == "GumroadStatsRequested":
            gumroad_client = context["engines"]["gumroad_client"]
            if gumroad_client is None:
                return [
                    Action(
                        type="GumroadStatsReady",
                        payload={"products": [], "sales": [], "balance": {}},
                    )
                ]

            products_payload = gumroad_client.get_products()
            sales_payload = gumroad_client.get_sales()
            balance_payload = gumroad_client.get_balance()

            return [
                Action(
                    type="GumroadStatsReady",
                    payload={
                        "products": products_payload.get("products", []),
                        "sales": sales_payload.get("sales", []),
                        "balance": balance_payload,
                    },
                )
            ]

        return []


def handle(event, context):
    return ScanHandler.handle(event, context)
