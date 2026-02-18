import tempfile
import unittest
from pathlib import Path

from core.control import Control
from core.events import Event
from core.execution_focus_engine import ExecutionFocusEngine
from core.domain.integrity import DomainIntegrityError
from core.product_launch_store import ProductLaunchStore
from core.product_proposal_store import ProductProposalStore


class ExecutionFocusEngineTest(unittest.TestCase):
    def test_select_active_priority(self):
        proposals = [
            {"id": "p1", "status": "approved"},
            {"id": "p2", "status": "building"},
        ]
        launches = [{"id": "l1", "status": "draft"}]

        self.assertEqual(ExecutionFocusEngine.select_active(proposals, launches), "p2")

    def test_enforce_single_active_marks_only_target(self):
        proposals = [{"id": "p1"}, {"id": "p2"}]
        launches = [{"id": "l1"}]

        ExecutionFocusEngine.enforce_single_active("p2", {"proposals": proposals, "launches": launches})

        self.assertFalse(proposals[0]["active_execution"])
        self.assertTrue(proposals[1]["active_execution"])
        self.assertFalse(launches[0]["active_execution"])


class ExecutionFocusStoreIntegrationTest(unittest.TestCase):
    def test_proposal_transition_sets_single_active_execution(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals = ProductProposalStore(path=root / "product_proposals.json")
            launches = ProductLaunchStore(proposal_store=proposals, path=root / "product_launches.json")
            control = Control(product_proposal_store=proposals, product_launch_store=launches)

            proposals.add({"id": "proposal-1", "product_name": "One"})
            proposals.add({"id": "proposal-2", "product_name": "Two"})

            control.consume(Event(type="ApproveProposal", payload={"proposal_id": "proposal-1"}, source="test"))
            with self.assertRaises(DomainIntegrityError):
                control.consume(Event(type="ApproveProposal", payload={"proposal_id": "proposal-2"}, source="test"))

            p1 = proposals.get("proposal-1")
            p2 = proposals.get("proposal-2")

            self.assertTrue(p1["active_execution"])
            self.assertFalse(p2["active_execution"])


if __name__ == "__main__":
    unittest.main()
