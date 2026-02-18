import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock

from core.control import Action, Control
from core.domain.integrity import DomainIntegrityError
from core.events import Event


class ControlSmokeTest(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self._data_dir = Path(self._temp_dir.name)

        self._original_data_dir = os.environ.get("TRETA_DATA_DIR")
        os.environ["TRETA_DATA_DIR"] = str(self._data_dir)
        self._clear_data_dir()

    def tearDown(self):
        if self._original_data_dir is None:
            os.environ.pop("TRETA_DATA_DIR", None)
        else:
            os.environ["TRETA_DATA_DIR"] = self._original_data_dir
        self._temp_dir.cleanup()

    def _clear_data_dir(self):
        self._data_dir.mkdir(parents=True, exist_ok=True)
        for child in self._data_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()

    def test_deterministic_mapping_for_requested_events(self):
        control = Control()

        cases = {
            "DailyBriefRequested": [Action(type="BuildDailyBrief", payload={"dry_run": True})],
            "OpportunityScanRequested": [Action(type="RunOpportunityScan", payload={"dry_run": True})],
            "EmailTriageRequested": [Action(type="RunEmailTriage", payload={"dry_run": True})],
        }

        for event_type, expected in cases.items():
            with self.subTest(event_type=event_type):
                event = Event(type=event_type, payload={}, source="test")
                first = control.consume(event)
                second = control.consume(event)

                self.assertEqual(first, expected)
                self.assertEqual(second, expected)
                self.assertEqual(first, second)

    def test_evaluate_opportunity_event_returns_structured_decision(self):
        control = Control()
        event = Event(
            type="EvaluateOpportunity",
            payload={
                "money": 8,
                "growth": 6,
                "energy": 3,
                "health": 2,
                "relationships": 5,
                "risk": 2,
            },
            source="test",
        )

        actions = control.consume(event)

        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].type, "OpportunityEvaluated")
        self.assertIn("score", actions[0].payload)
        self.assertIn("decision", actions[0].payload)
        self.assertIn("reasoning", actions[0].payload)

    def test_action_approved_generates_action_plan(self):
        control = Control()
        event = Event(type="ActionApproved", payload={"type": "top_product"}, source="test")

        actions = control.consume(event)

        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].type, "ActionPlanGenerated")
        self.assertEqual(
            actions[0].payload,
            {
                "action": "optimize",
                "steps": [
                    "Add upsell",
                    "Improve landing page copy",
                    "Collect testimonials",
                ],
                "priority": 9,
            },
        )

    def test_gumroad_stats_requested_returns_structured_payload(self):
        gumroad_client = Mock()
        gumroad_client.get_products.return_value = {"products": [{"id": "p1"}]}
        gumroad_client.get_sales.return_value = {"sales": [{"id": "s1"}], "limit": 10}
        gumroad_client.get_balance.return_value = {"balance": 123.45, "currency": "USD"}

        control = Control(gumroad_client=gumroad_client)
        event = Event(type="GumroadStatsRequested", payload={}, source="test")

        actions = control.consume(event)

        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].type, "GumroadStatsReady")
        self.assertEqual(
            actions[0].payload,
            {
                "products": [{"id": "p1"}],
                "sales": [{"id": "s1"}],
                "balance": {"balance": 123.45, "currency": "USD"},
            },
        )

        gumroad_client.get_products.assert_called_once_with()
        gumroad_client.get_sales.assert_called_once_with()
        gumroad_client.get_balance.assert_called_once_with()


    def test_opportunity_detected_filters_non_aligned_opportunity(self):
        control = Control()

        payload = {
            "id": "opp-filter",
            "source": "scanner",
            "title": "General productivity app idea",
            "summary": "Build a broad social consumer app",
            "opportunity": {"money": 2, "growth": 2, "confidence": 3},
        }

        actions = control.consume(Event(type="OpportunityDetected", payload=payload, source="test"))
        self.assertEqual(actions, [])

        listed = control.consume(Event(type="ListOpportunities", payload={}, source="test"))
        items = {item["id"]: item for item in listed[0].payload["items"]}
        self.assertEqual(items["opp-filter"]["status"], "strategically_filtered")

    def test_opportunity_detected_stores_alignment_metadata_on_generated_proposal(self):
        control = Control()

        payload = {
            "id": "opp-aligned",
            "source": "scanner",
            "title": "Client onboarding system kit for creators",
            "summary": "Automation that improves client acquisition and revenue",
            "opportunity": {"confidence": 8},
        }

        actions = control.consume(Event(type="OpportunityDetected", payload=payload, source="test"))
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].type, "ProductProposalGenerated")
        proposal = actions[0].payload["proposal"]
        self.assertIn("alignment_score", proposal)
        self.assertIn("alignment_reason", proposal)
        self.assertGreaterEqual(proposal["alignment_score"], 60)

    def test_opportunity_store_flow_detect_list_evaluate_and_dismiss(self):
        control = Control()

        first_payload = {
            "id": "opp-1",
            "source": "scanner",
            "title": "Client onboarding system kit for creators",
            "summary": "Automation template that improves revenue and client acquisition",
            "opportunity": {
                "money": 8,
                "growth": 7,
                "energy": 2,
                "health": 3,
                "relationships": 6,
                "risk": 2,
            },
        }
        second_payload = {
            "id": "opp-2",
            "source": "scanner",
            "title": "Freelance proposal template pack",
            "summary": "Template system for service professionals to increase client acquisition",
            "opportunity": {
                "money": 3,
                "growth": 4,
                "energy": 7,
                "health": 2,
                "relationships": 3,
                "risk": 6,
            },
        }

        control.consume(Event(type="OpportunityDetected", payload=first_payload, source="test"))
        control.consume(Event(type="OpportunityDetected", payload=second_payload, source="test"))

        listed = control.consume(Event(type="ListOpportunities", payload={}, source="test"))
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0].type, "OpportunitiesListed")
        items = listed[0].payload["items"]
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["status"], "new")
        self.assertEqual(items[1]["status"], "new")

        evaluated = control.consume(
            Event(type="EvaluateOpportunityById", payload={"id": "opp-1"}, source="test")
        )
        self.assertEqual(len(evaluated), 1)
        self.assertEqual(evaluated[0].type, "OpportunityEvaluated")
        self.assertEqual(evaluated[0].payload["item"]["status"], "evaluated")
        self.assertIn("score", evaluated[0].payload["decision"])
        self.assertIn("decision", evaluated[0].payload["decision"])

        control.consume(Event(type="OpportunityDismissed", payload={"id": "opp-2"}, source="test"))

        final_listed = control.consume(Event(type="ListOpportunities", payload={}, source="test"))
        final_items = {item["id"]: item for item in final_listed[0].payload["items"]}
        self.assertEqual(final_items["opp-1"]["status"], "evaluated")
        self.assertIsNotNone(final_items["opp-1"]["decision"])
        self.assertEqual(final_items["opp-2"]["status"], "dismissed")
        self.assertIsNone(final_items["opp-2"]["decision"])


    def test_build_product_plan_requires_preapproved_status(self):
        control = Control()
        control.product_proposal_store.add({"id": "proposal-draft", "product_name": "Draft", "status": "draft"})

        with self.assertRaises(DomainIntegrityError):
            control.consume(Event(type="BuildProductPlanRequested", payload={"proposal_id": "proposal-draft"}, source="test"))


if __name__ == "__main__":
    unittest.main()
