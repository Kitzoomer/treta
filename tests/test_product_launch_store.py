import tempfile
import unittest
from pathlib import Path

from core.control import Control
from core.events import Event
from core.product_launch_store import ProductLaunchStore
from core.product_proposal_store import ProductProposalStore


class ProductLaunchStoreTest(unittest.TestCase):
    def _stores(self, root: Path):
        proposals = ProductProposalStore(path=root / "product_proposals.json")
        launches = ProductLaunchStore(proposal_store=proposals, path=root / "product_launches.json")
        return proposals, launches

    def test_launch_created_only_when_proposal_explicitly_launched(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            proposals.add({"id": "proposal-1", "product_name": "Launch Kit"})
            control = Control(product_proposal_store=proposals, product_launch_store=launches)

            control.consume(Event(type="ApproveProposal", payload={"proposal_id": "proposal-1"}, source="test"))
            control.consume(Event(type="StartBuildingProposal", payload={"proposal_id": "proposal-1"}, source="test"))
            control.consume(Event(type="MarkReadyToLaunch", payload={"proposal_id": "proposal-1"}, source="test"))
            execute_actions = control.consume(Event(type="ExecuteProductPlanRequested", payload={"proposal_id": "proposal-1"}, source="test"))

            self.assertTrue(any(action.type == "ProductPlanExecuted" for action in execute_actions))
            self.assertTrue(any(action.type == "ProductProposalStatusChanged" and action.payload["status"] == "ready_for_review" for action in execute_actions))
            self.assertIsNone(launches.get_by_proposal_id("proposal-1"))

            actions = control.consume(Event(type="MarkProposalLaunched", payload={"proposal_id": "proposal-1"}, source="test"))
            self.assertTrue(any(action.type == "ProductProposalStatusChanged" and action.payload["status"] == "launched" for action in actions))
            self.assertTrue(any(action.type == "ProductLaunched" for action in actions))
            launch = launches.get_by_proposal_id("proposal-1")
            self.assertIsNotNone(launch)
            self.assertEqual(launch["status"], "active")
            self.assertIsNotNone(launch["launched_at"])

    def test_add_sale_increases_sales_and_revenue(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            proposals.add({"id": "proposal-2", "product_name": "Sales Kit"})
            created = launches.add_from_proposal("proposal-2")

            updated = launches.add_sale(created["id"], 29)

            self.assertEqual(updated["metrics"]["sales"], 1)
            self.assertEqual(updated["metrics"]["revenue"], 29.0)

    def test_persistence_works(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            proposals.add({"id": "proposal-3", "product_name": "Persist Kit"})
            created = launches.add_from_proposal("proposal-3")
            launches.mark_launched(created["id"])
            launches.add_sale(created["id"], 10)

            reloaded_proposals = ProductProposalStore(path=root / "product_proposals.json")
            reloaded_launches = ProductLaunchStore(
                proposal_store=reloaded_proposals,
                path=root / "product_launches.json",
            )
            loaded = reloaded_launches.get(created["id"])

            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["metrics"]["sales"], 1)
            self.assertEqual(loaded["metrics"]["revenue"], 10.0)
            self.assertEqual(loaded["status"], "active")

    def test_invalid_status_raises_value_error(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            proposals.add({"id": "proposal-4", "product_name": "Status Kit"})
            created = launches.add_from_proposal("proposal-4")

            with self.assertRaises(ValueError):
                launches.transition_status(created["id"], "invalid")


if __name__ == "__main__":
    unittest.main()
