from __future__ import annotations

import time
import logging

import core.config as config

from core.action_execution_store import ActionExecutionStore
from core.autonomy_policy_engine import AutonomyPolicyEngine
from core.bus import EventBus
from core.config import get_autonomy_mode
from core.control import Control
from core.conversation_core import ConversationCore
from core.daily_loop import DailyLoopEngine
from core.gpt_client import GPTClient, GPTClientConfigurationError
from core.dispatcher import Dispatcher
from core.decision_engine import DecisionEngine
from core.events import Event
from core.ipc_http import start_http_server
from core.memory_store import MemoryStore
from core.model_policy_engine import ModelPolicyEngine
from core.migrations.runner import run_migrations
from core.opportunity_store import OpportunityStore
from core.performance_engine import PerformanceEngine
from core.product_launch_store import ProductLaunchStore
from core.product_plan_store import ProductPlanStore
from core.product_proposal_store import ProductProposalStore
from core.scheduler import DailyScheduler
from core.state_machine import State, StateMachine
from core.storage import Storage
from core.executors.draft_asset_executor import DraftAssetExecutor
from core.executors.registry import ActionExecutorRegistry
from core.strategy_action_execution_layer import StrategyActionExecutionLayer
from core.strategy_action_store import StrategyActionStore
from core.strategy_decision_engine import StrategyDecisionEngine
from core.strategy_engine import StrategyEngine
from core.revenue_attribution.store import RevenueAttributionStore
from core.subreddit_performance_store import SubredditPerformanceStore


def bootstrap_executors(registry: ActionExecutorRegistry, app_config=config) -> None:
    registry.register(DraftAssetExecutor())

    if str(app_config.OPENCLAW_BASE_URL or "").strip():
        from core.executors.openclaw_executor import OpenClawExecutor

        registry.register(OpenClawExecutor())
        return

    logging.getLogger("treta.executors").warning("OpenClaw executor disabled")


class TretaApp:
    def __init__(self, storage: Storage | None = None):
        self.storage = storage or Storage()
        conn = self.storage.conn
        run_migrations(conn)
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        wal_mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
        logging.getLogger("treta.storage").info("SQLite startup mode", extra={"journal_mode": wal_mode})

        self.bus = EventBus()

        last_state = self.storage.get_state("last_state") or State.IDLE
        self.state_machine = StateMachine(initial_state=last_state)
        self.opportunity_store = OpportunityStore()
        self.product_proposal_store = ProductProposalStore()
        self.product_plan_store = ProductPlanStore()
        self.product_launch_store = ProductLaunchStore(proposal_store=self.product_proposal_store)
        self.revenue_attribution_store = RevenueAttributionStore()
        self.subreddit_performance_store = SubredditPerformanceStore()
        self.performance_engine = PerformanceEngine(product_launch_store=self.product_launch_store)
        self.strategy_engine = StrategyEngine(product_launch_store=self.product_launch_store)
        self.strategy_action_store = StrategyActionStore()
        self.model_policy_engine = ModelPolicyEngine()
        self.action_execution_store = ActionExecutionStore(self.storage.conn)
        self.executor_registry = ActionExecutorRegistry()
        bootstrap_executors(self.executor_registry, config)
        self.daily_loop_engine = DailyLoopEngine(
            opportunity_store=self.opportunity_store,
            proposal_store=self.product_proposal_store,
            launch_store=self.product_launch_store,
            strategy_store=self.strategy_action_store,
        )
        self.strategy_action_execution_layer = StrategyActionExecutionLayer(
            strategy_action_store=self.strategy_action_store,
            bus=self.bus,
            storage=self.storage,
            action_execution_store=self.action_execution_store,
            executor_registry=self.executor_registry,
        )
        self.autonomy_policy_engine = AutonomyPolicyEngine(
            strategy_action_store=self.strategy_action_store,
            strategy_action_execution_layer=self.strategy_action_execution_layer,
            mode=get_autonomy_mode(),
            bus=self.bus,
            storage=self.storage,
        )
        self.strategy_decision_engine = StrategyDecisionEngine(
            product_launch_store=self.product_launch_store,
            strategy_action_execution_layer=self.strategy_action_execution_layer,
            autonomy_policy_engine=self.autonomy_policy_engine,
            storage=self.storage,
        )
        self.decision_engine = DecisionEngine(storage=self.storage)
        self.memory_store = MemoryStore()
        self.control = Control(
            opportunity_store=self.opportunity_store,
            product_proposal_store=self.product_proposal_store,
            product_plan_store=self.product_plan_store,
            product_launch_store=self.product_launch_store,
            revenue_attribution_store=self.revenue_attribution_store,
            subreddit_performance_store=self.subreddit_performance_store,
            strategy_decision_engine=self.strategy_decision_engine,
            strategy_action_execution_layer=self.strategy_action_execution_layer,
            bus=self.bus,
            decision_engine=self.decision_engine,
        )
        try:
            gpt_client = GPTClient(
                revenue_attribution_store=self.revenue_attribution_store,
                model_policy_engine=self.model_policy_engine,
            )
        except GPTClientConfigurationError:
            gpt_client = None

        self.conversation_core = ConversationCore(
            bus=self.bus,
            state_machine=self.state_machine,
            memory_store=self.memory_store,
            gpt_client_optional=gpt_client,
            daily_loop_engine=self.daily_loop_engine,
        )
        self.dispatcher = Dispatcher(
            state_machine=self.state_machine,
            control=self.control,
            memory_store=self.memory_store,
            conversation_core=self.conversation_core,
            bus=self.bus,
            storage=self.storage,
        )
        self.scheduler = DailyScheduler(bus=self.bus)
        self.http_server = None

    def start_http_server(self, host: str = "0.0.0.0", port: int = 7777, action_execution_store=None):
        self.http_server = start_http_server(
            host=host,
            port=port,
            bus=self.bus,
            state_machine=self.state_machine,
            opportunity_store=self.opportunity_store,
            product_proposal_store=self.product_proposal_store,
            product_plan_store=self.product_plan_store,
            product_launch_store=self.product_launch_store,
            performance_engine=self.performance_engine,
            control=self.control,
            strategy_engine=self.strategy_engine,
            strategy_decision_engine=self.strategy_decision_engine,
            strategy_action_execution_layer=self.strategy_action_execution_layer,
            autonomy_policy_engine=self.autonomy_policy_engine,
            daily_loop_engine=self.daily_loop_engine,
            memory_store=self.memory_store,
            conversation_core=self.conversation_core,
            revenue_attribution_store=self.revenue_attribution_store,
            subreddit_performance_store=self.subreddit_performance_store,
            storage=self.storage,
            action_execution_store=self.action_execution_store,
            model_policy_engine=self.model_policy_engine,
        )
        return self.http_server

    def run(self):
        self.scheduler.start()
        self.start_http_server()
        try:
            while True:
                event = self.bus.pop(timeout=0.2)
                if event is not None:
                    self.dispatcher.handle(event)
                    continue

                time.sleep(5)
                heartbeat = Event(
                    type="Heartbeat",
                    payload={"state": self.state_machine.state},
                    source="core",
                )
                logging.getLogger("treta.event").info(
                    "Heartbeat",
                    extra={"event_type": heartbeat.type, "state": self.state_machine.state},
                )
                self.storage.set_state("last_state", self.state_machine.state)
        finally:
            self.scheduler.stop()
            self.storage.set_state("last_state", self.state_machine.state)
