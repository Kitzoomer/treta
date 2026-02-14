import tempfile
import unittest
from pathlib import Path

from core.control import Control
from core.events import Event
from core.product_proposal_store import ProductProposalStore


class ProductProposalLifecycleTest(unittest.TestCase):
    def _create_store(self, root: Path) -> ProductProposalStore:
        return ProductProposalStore(path=root / "product_proposals.json")

    def test_valid_transition_sequence(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._create_store(Path(tmp_dir))
            proposal = store.add({"id": "proposal-1", "product_name": "Demo"})

            self.assertEqual(proposal["status"], "draft")

            for status in ["approved", "building", "ready_to_launch", "ready_for_review", "launched", "archived"]:
                proposal = store.transition_status("proposal-1", status)
                self.assertEqual(proposal["status"], status)

    def test_invalid_transition_raises_value_error(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._create_store(Path(tmp_dir))
            store.add({"id": "proposal-2", "product_name": "Demo"})

            with self.assertRaises(ValueError):
                store.transition_status("proposal-2", "building")

    def test_transition_is_persisted(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = self._create_store(root)
            store.add({"id": "proposal-3", "product_name": "Demo"})
            updated = store.transition_status("proposal-3", "approved")

            reloaded_store = self._create_store(root)
            persisted = reloaded_store.get("proposal-3")

            self.assertIsNotNone(persisted)
            self.assertEqual(persisted["status"], "approved")
            self.assertEqual(persisted["updated_at"], updated["updated_at"])

    def test_status_changed_event_emitted_by_control(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._create_store(Path(tmp_dir))
            store.add({"id": "proposal-4", "product_name": "Demo"})
            control = Control(product_proposal_store=store)

            actions = control.consume(
                Event(type="ApproveProposal", payload={"proposal_id": "proposal-4"}, source="test")
            )

            self.assertEqual(len(actions), 1)
            self.assertEqual(actions[0].type, "ProductProposalStatusChanged")
            self.assertEqual(actions[0].payload["proposal_id"], "proposal-4")
            self.assertEqual(actions[0].payload["status"], "approved")


if __name__ == "__main__":
    unittest.main()
