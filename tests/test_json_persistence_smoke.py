import tempfile
import unittest
from pathlib import Path

from core.execution_engine import ExecutionEngine
from core.memory_store import MemoryStore
from core.opportunity_store import OpportunityStore
from core.product_launch_store import ProductLaunchStore
from core.product_plan_store import ProductPlanStore
from core.product_proposal_store import ProductProposalStore
from core.strategy_action_store import StrategyActionStore


class JsonPersistenceSmokeTest(unittest.TestCase):
    def test_store_and_execution_history_reload_from_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            opportunities_path = root / "opportunities.json"
            proposals_path = root / "product_proposals.json"
            launches_path = root / "product_launches.json"
            actions_path = root / "strategy_actions.json"
            plans_path = root / "product_plans.json"
            memory_path = root / "memory_store.json"
            executions_path = root / "executions.json"

            opportunity_store = OpportunityStore(path=opportunities_path)
            product_proposal_store = ProductProposalStore(path=proposals_path)
            launch_store = ProductLaunchStore(proposal_store=product_proposal_store, path=launches_path)
            action_store = StrategyActionStore(path=actions_path)
            plan_store = ProductPlanStore(path=plans_path)
            memory_store = MemoryStore(path=memory_path)
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
            created_launch = launch_store.add_from_proposal(created_proposal["id"])
            created_action = action_store.add(
                action_type="review",
                target_id=created_proposal["id"],
                reasoning="Smoke test action",
            )
            created_plan = plan_store.add(
                {
                    "plan_id": "plan-persist-1",
                    "proposal_id": created_proposal["id"],
                    "step": "publish",
                }
            )
            created_message = memory_store.append_message("user", "hola")
            execution_package = execution_engine.generate_execution_package(created_proposal)

            reloaded_opportunity_store = OpportunityStore(path=opportunities_path)
            reloaded_product_proposal_store = ProductProposalStore(path=proposals_path)
            reloaded_launch_store = ProductLaunchStore(
                proposal_store=reloaded_product_proposal_store,
                path=launches_path,
            )
            reloaded_action_store = StrategyActionStore(path=actions_path)
            reloaded_plan_store = ProductPlanStore(path=plans_path)
            reloaded_memory_store = MemoryStore(path=memory_path)
            reloaded_execution_engine = ExecutionEngine(path=executions_path)

            self.assertEqual(reloaded_opportunity_store.get(created_opportunity["id"]), created_opportunity)
            self.assertEqual(reloaded_product_proposal_store.get(created_proposal["id"]), created_proposal)
            self.assertEqual(reloaded_launch_store.get(created_launch["id"]), created_launch)
            self.assertEqual(reloaded_action_store.get(created_action["id"]), created_action)
            self.assertEqual(reloaded_plan_store.get(created_plan["plan_id"]), created_plan)

            reloaded_messages = reloaded_memory_store.snapshot()["chat_history"]
            self.assertEqual(len(reloaded_messages), 1)
            self.assertEqual(reloaded_messages[0], created_message)

            history = reloaded_execution_engine.list_history()
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["proposal_id"], created_proposal["id"])
            self.assertEqual(history[0]["execution_package"], execution_package)

    def test_corrupt_json_store_is_quarantined(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            opportunities_path = root / "opportunities.json"
            proposals_path = root / "product_proposals.json"
            launches_path = root / "product_launches.json"
            actions_path = root / "strategy_actions.json"
            memory_path = root / "memory_store.json"

            for path in [opportunities_path, proposals_path, launches_path, actions_path, memory_path]:
                path.write_text("{not-json", encoding="utf-8")

            opportunity_store = OpportunityStore(path=opportunities_path)
            proposal_store = ProductProposalStore(path=proposals_path)
            launch_store = ProductLaunchStore(proposal_store=proposal_store, path=launches_path)
            action_store = StrategyActionStore(path=actions_path)
            memory_store = MemoryStore(path=memory_path)

            self.assertEqual(opportunity_store.list(), [])
            self.assertEqual(proposal_store.list(), [])
            self.assertEqual(launch_store.list(), [])
            self.assertEqual(action_store.list(), [])
            self.assertEqual(memory_store.snapshot()["chat_history"], [])

            for path in [opportunities_path, proposals_path, launches_path, actions_path, memory_path]:
                self.assertFalse(path.exists())
                self.assertEqual(len(list(root.glob(f"{path.name}*.corrupt"))), 1)

    def test_memory_store_search_chat_history_orders_by_score_and_recency(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            memory_store = MemoryStore(path=Path(tmp_dir) / "memory_store.json")
            memory_store.append_message("user", "Necesito mejorar pricing para gumroad")
            memory_store.append_message("assistant", "Vale, revisemos pricing por segmento")
            memory_store.append_message("user", "Quiero ideas de contenido")
            memory_store.append_message("assistant", "Podemos validar pricing y oferta")

            results = memory_store.search_chat_history("pricing", limit=3)

            self.assertEqual(len(results), 3)
            self.assertEqual(results[0]["content"], "Podemos validar pricing y oferta")
            self.assertEqual(results[1]["content"], "Vale, revisemos pricing por segmento")
            self.assertEqual(results[2]["content"], "Necesito mejorar pricing para gumroad")


if __name__ == "__main__":
    unittest.main()
