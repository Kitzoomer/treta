import threading
import time
import unittest

from core.events import Event
from core.strategic_loop_engine import StrategicLoopEngine


class _FakeLayer:
    def __init__(self):
        self.pending = []

    def list_pending_actions(self):
        return list(self.pending)


class _CooldownAwareControl:
    def __init__(self):
        self.strategy_action_execution_layer = _FakeLayer()
        self.calls = []
        self.executed_count = 0
        self.cooldown_skips = 0
        self._last_decision_at = None

    def consume(self, event: Event):
        self.calls.append(event.type)
        now = time.monotonic()
        if self._last_decision_at is None:
            self._last_decision_at = now
            self.executed_count += 1
            return [{"status": "executed"}]

        if now - self._last_decision_at < 1.0:
            self.cooldown_skips += 1
            return [{"status": "skipped", "reason": "cooldown_active"}]

        self._last_decision_at = now
        self.executed_count += 1
        return [{"status": "executed"}]




class _CountingLock:
    def __init__(self):
        self._lock = threading.Lock()
        self.max_concurrent = 0
        self._current = 0

    def acquire(self, blocking=True):
        acquired = self._lock.acquire(blocking=blocking)
        if acquired:
            self._current += 1
            self.max_concurrent = max(self.max_concurrent, self._current)
        return acquired

    def release(self):
        self._current -= 1
        self._lock.release()


class StrategicLoopEngineTest(unittest.TestCase):

    def test_two_quick_cycles_respect_cooldown_without_breaking_cycle_lock(self):
        control = _CooldownAwareControl()
        cycle_lock = _CountingLock()
        engine = StrategicLoopEngine(control=control, interval_seconds=0.02, max_pending=99, cycle_lock=cycle_lock)
        engine.start()
        try:
            time.sleep(0.09)
        finally:
            engine.stop()

        self.assertGreaterEqual(len(control.calls), 2)
        self.assertGreaterEqual(control.cooldown_skips, 1)
        self.assertEqual(control.executed_count, 1)
        self.assertEqual(cycle_lock.max_concurrent, 1)

    def test_runs_two_quick_cycles_without_breaking_cooldown(self):
        control = _CooldownAwareControl()
        engine = StrategicLoopEngine(control=control, interval_seconds=0.02, max_pending=99)
        engine.start()
        try:
            time.sleep(0.09)
        finally:
            engine.stop()

        self.assertGreaterEqual(len(control.calls), 2)
        self.assertEqual(control.calls[0], "RunStrategyDecision")
        self.assertGreaterEqual(control.cooldown_skips, 1)
        self.assertEqual(control.executed_count, 1)

    def test_skips_when_pending_threshold_reached(self):
        control = _CooldownAwareControl()
        control.strategy_action_execution_layer.pending = [{"id": "a1"}, {"id": "a2"}]
        engine = StrategicLoopEngine(control=control, interval_seconds=0.02, max_pending=2)
        engine.start()
        try:
            time.sleep(0.06)
        finally:
            engine.stop()

        self.assertEqual(control.calls, [])


if __name__ == "__main__":
    unittest.main()
