import tempfile
import unittest
from pathlib import Path

from core.execution_engine import ExecutionEngine
from core.opportunity_store import OpportunityStore
from core.product_proposal_store import ProductProposalStore


class JsonPersistenceSmokeTest(unittest.TestCase):
    def test_store_and_execution_history_reload_from_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            opportunities_path = root / "opportunities.json"
            proposals_path = root / "product_proposals.json"
            executions_path = root / "executions.json"

            opportunity_store = OpportunityStore(path=opportunities_path)
            product_proposal_store = ProductProposalStore(path=proposals_path)
            execution_engine = ExecutionEngine(path=executions_path)

            created_opportunity = opportunity_store.add(
                item_id="opp-persist-1",
                source="test",
                title="Persisted opportunity",
                summary="A stored opportunity",
                opportunity={"money": 7, "growth": 6},
            )
            created_proposal = product_proposal_store.add(
                {
                    "id": "proposal-persist-1",
                    "product_name": "Proposal Pack",
                    "target_audience": "Freelancers",
                    "price_suggestion": 29,
                    "reasoning": "Persistence smoke test",
                }
            )
            execution_package = execution_engine.generate_execution_package(created_proposal)

            reloaded_opportunity_store = OpportunityStore(path=opportunities_path)
            reloaded_product_proposal_store = ProductProposalStore(path=proposals_path)
            reloaded_execution_engine = ExecutionEngine(path=executions_path)

            self.assertEqual(
                reloaded_opportunity_store.get(created_opportunity["id"]),
                created_opportunity,
            )
            self.assertEqual(
                reloaded_product_proposal_store.get(created_proposal["id"]),
                created_proposal,
            )

            history = reloaded_execution_engine.list_history()
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["proposal_id"], created_proposal["id"])
            self.assertEqual(history[0]["execution_package"], execution_package)


if __name__ == "__main__":
    unittest.main()
