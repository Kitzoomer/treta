from __future__ import annotations

import pytest

try:
    from core.bus import EventBus
    from core.scheduler import DailyScheduler
except Exception as exc:  # pragma: no cover
    EventBus = None
    DailyScheduler = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


@pytest.mark.xfail(DailyScheduler is None, reason=f"scheduler module unavailable: {IMPORT_ERROR}")
def test_scheduler_tick_smoke() -> None:
    bus = EventBus()
    scheduler = DailyScheduler(bus=bus)
    scheduler.tick()
    assert scheduler._next_scan_at is not None
