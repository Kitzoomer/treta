from __future__ import annotations

import logging
import threading
import time

from core.events import Event


class StrategicLoopEngine:
    def __init__(self, control, interval_seconds: float, max_pending: int, logger=None, cycle_lock=None):
        self.control = control
        self.interval_seconds = max(0.01, float(interval_seconds))
        self.max_pending = max(0, int(max_pending))
        self.logger = logger or logging.getLogger("treta.strategic_loop")
        self.cycle_lock = cycle_lock
        self._running = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=max(0.1, self.interval_seconds * 2))

    def _pending_actions_count(self) -> int:
        layer = getattr(self.control, "strategy_action_execution_layer", None)
        if layer is None or not hasattr(layer, "list_pending_actions"):
            return 0
        pending = layer.list_pending_actions()
        return len(pending) if isinstance(pending, list) else 0

    def _run_loop(self) -> None:
        while self._running and not self._stop_event.is_set():
            try:
                pending_actions_count = self._pending_actions_count()
                if pending_actions_count >= self.max_pending:
                    self.logger.info(
                        "skip: too many pending",
                        extra={
                            "pending_actions_count": pending_actions_count,
                            "max_pending": self.max_pending,
                        },
                    )
                else:
                    lock_acquired = False
                    if self.cycle_lock is not None:
                        lock_acquired = self.cycle_lock.acquire(blocking=False)
                        if not lock_acquired:
                            self.logger.info("skip: cycle_lock_active")
                        else:
                            try:
                                self.control.consume(Event(type="RunStrategyDecision", payload={}))
                            finally:
                                self.cycle_lock.release()
                    else:
                        self.control.consume(Event(type="RunStrategyDecision", payload={}))
            except Exception:
                self.logger.exception("strategic loop iteration failed")

            if self._stop_event.wait(timeout=self.interval_seconds):
                break

