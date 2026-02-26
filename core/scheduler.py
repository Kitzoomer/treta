import logging
import os
import threading
import uuid
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from core.bus import EventBus
from core.events import Event
from core.logging_config import set_request_id
from core.scheduler_state import load_scheduler_state, save_scheduler_state


logger = logging.getLogger("treta.scheduler")


class DailyScheduler:
    def __init__(self, bus: EventBus | None = None, now_fn=None, sleep_fn=None):
        self.timezone_name = os.getenv("TRETA_TIMEZONE", "UTC")
        self.scan_hour = int(os.getenv("TRETA_SCAN_HOUR", "9"))
        self._timezone = ZoneInfo(self.timezone_name)

        self._now_fn = now_fn
        self._sleep_fn = sleep_fn or time.sleep

        self._bus = bus
        self._stop_event = threading.Event()
        self._thread = None
        self._last_run_date = None
        self._last_run_timestamp = None
        self._next_scan_at = None

        state = load_scheduler_state()
        last_run_date = state.get("last_run_date")
        if isinstance(last_run_date, str):
            try:
                self._last_run_date = datetime.fromisoformat(last_run_date).date()
            except ValueError:
                self._last_run_date = None
        self._last_run_timestamp = state.get("last_run_timestamp")

    def start(self, bus: EventBus | None = None):
        if self._thread and self._thread.is_alive():
            return

        if bus is not None:
            self._bus = bus
        if self._bus is None:
            self._bus = EventBus()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _now(self):
        if self._now_fn is not None:
            return self._now_fn()
        return datetime.now(self._timezone)

    def _scheduled_for_day(self, now):
        return now.replace(hour=self.scan_hour, minute=0, second=0, microsecond=0)

    def _next_scheduled_at(self, now):
        scheduled_today = self._scheduled_for_day(now)
        if now < scheduled_today:
            return scheduled_today
        return scheduled_today + timedelta(days=1)

    def _run_due_scan_if_needed(self, now):
        if self._last_run_date == now.date():
            return False

        if now >= self._scheduled_for_day(now):
            request_id = str(uuid.uuid4())
            set_request_id(request_id)
            logger.info("Running daily scan", extra={"event_type": "scheduler_scan", "request_id": request_id})
            self._bus.push(Event(type="RunInfoproductScan", payload={"request_id": request_id}, source="scheduler", request_id=request_id))
            self._last_run_date = now.date()
            self._last_run_timestamp = now.isoformat()
            save_scheduler_state(self._last_run_date.isoformat(), self._last_run_timestamp)
            return True

        return False

    def tick(self):
        now = self._now()
        self._run_due_scan_if_needed(now)
        self._next_scan_at = self._next_scheduled_at(now)
        logger.info("Next scan scheduled", extra={"next_scan_at": self._next_scan_at.isoformat()})

    def _run_loop(self):
        while not self._stop_event.is_set():
            now = self._now()
            self._run_due_scan_if_needed(now)

            self._next_scan_at = self._next_scheduled_at(now)
            logger.info("Next scan scheduled", extra={"next_scan_at": self._next_scan_at.isoformat()})

            sleep_seconds = max((self._next_scan_at - now).total_seconds(), 0)
            # Wake periodically so stop() is responsive.
            self._stop_event.wait(timeout=min(sleep_seconds, 60))
