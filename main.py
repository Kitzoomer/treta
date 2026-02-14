import time
from core.state_machine import StateMachine, State
from core.storage import Storage
from core.events import Event
from core.ipc_http import start_http_server
from core.bus import event_bus
from core.dispatcher import Dispatcher
from core.control import Control
from core.opportunity_store import OpportunityStore
from core.scheduler import DailyScheduler
from core.product_proposal_store import ProductProposalStore
from core.product_plan_store import ProductPlanStore
from core.product_launch_store import ProductLaunchStore
from core.performance_engine import PerformanceEngine
from core.strategy_engine import StrategyEngine
from core.strategy_decision_engine import StrategyDecisionEngine


def main():
    print("🧠 Treta Core starting...")

    storage = Storage()
    last_state = storage.get_state("last_state") or State.IDLE

    sm = StateMachine(initial_state=last_state)
    opportunity_store = OpportunityStore()
    product_proposal_store = ProductProposalStore()
    product_plan_store = ProductPlanStore()
    product_launch_store = ProductLaunchStore(proposal_store=product_proposal_store)
    performance_engine = PerformanceEngine(product_launch_store=product_launch_store)
    strategy_engine = StrategyEngine(product_launch_store=product_launch_store)
    strategy_decision_engine = StrategyDecisionEngine(product_launch_store=product_launch_store)
    control = Control(
        opportunity_store=opportunity_store,
        product_proposal_store=product_proposal_store,
        product_plan_store=product_plan_store,
        product_launch_store=product_launch_store,
    )
    dispatcher = Dispatcher(state_machine=sm, control=control)
    print(f"🧠 Restored state: {sm.state}")
    print("[BOOT] Starting HTTP server")
    scheduler = DailyScheduler()
    scheduler.start(event_bus)
    try:
        start_http_server(
            state_machine=sm,
            opportunity_store=opportunity_store,
            product_proposal_store=product_proposal_store,
            product_plan_store=product_plan_store,
            product_launch_store=product_launch_store,
            performance_engine=performance_engine,
            control=control,
            strategy_engine=strategy_engine,
            strategy_decision_engine=strategy_decision_engine,
        )
    except TypeError:
        start_http_server()

    try:
        while True:
            event = event_bus.pop(timeout=0.2)
            if event is not None:
                dispatcher.handle(event)
                continue

            # Loop principal (siempre activa)
            time.sleep(5)

            # Evento dummy (por ahora)
            heartbeat = Event(
                type="Heartbeat",
                payload={"state": sm.state},
                source="core"
            )

            print(f"[EVENT] {heartbeat.type} | state={sm.state}")

            # Persistimos estado
            storage.set_state("last_state", sm.state)

    except KeyboardInterrupt:
        print("🛑 Treta Core stopped by user")
    finally:
        scheduler.stop()
        storage.set_state("last_state", sm.state)


if __name__ == "__main__":
    main()
