from __future__ import annotations

from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sqlite3
from typing import Any, Dict, List

from core.persistence.json_io import atomic_read_json, atomic_write_json, quarantine_corrupt_file
from core.risk_evaluation_engine import RiskEvaluationEngine


StrategyAction = Dict[str, Any]

logger = logging.getLogger(__name__)


class StrategyActionStore:
    """Persistent bounded store for strategy actions requiring confirmation."""

    _DEFAULT_DATA_DIR = "./.treta_data"
    _ALLOWED_TYPES = {"scale", "review", "price_test", "new_product", "archive"}
    _ALLOWED_STATUSES = {"pending_confirmation", "executed", "auto_executed", "completed", "failed", "rejected"}

    def __init__(self, capacity: int = 200, path: Path | None = None):
        data_dir = Path(os.getenv("TRETA_DATA_DIR", self._DEFAULT_DATA_DIR))
        self._path = path or data_dir / "strategy_actions.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._risk_evaluation_engine = RiskEvaluationEngine()
        self._sqlite_enabled = False
        self._conn: sqlite3.Connection | None = None

        db_path = self._resolve_db_path(data_dir=data_dir, json_path=self._path)
        loaded_from_sqlite: list[StrategyAction] = []
        try:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(db_path, check_same_thread=False)
            self._sqlite_enabled = True
            self._ensure_sqlite_table()
            loaded_from_sqlite = self._load_items_from_sqlite()
            logger.info("StrategyActions now SQLite-only (JSON deprecated)", extra={"db_path": str(db_path)})
        except sqlite3.Error as exc:
            self._sqlite_enabled = False
            self._conn = None
            logger.warning("StrategyActions SQLite unavailable; using legacy JSON fallback", extra={"error": str(exc), "db_path": str(db_path)})

        if self._sqlite_enabled and loaded_from_sqlite:
            initial_items = loaded_from_sqlite
        else:
            initial_items = self._load_items_from_json()
            if self._sqlite_enabled and initial_items:
                self._migrate_json_to_sqlite(initial_items)

        self._items: deque[StrategyAction] = deque(initial_items, maxlen=capacity)

    def _resolve_db_path(self, *, data_dir: Path, json_path: Path) -> Path:
        if json_path.is_absolute():
            return json_path.parent / "memory" / "treta.sqlite"
        return data_dir / "memory" / "treta.sqlite"

    def _ensure_sqlite_table(self) -> None:
        assert self._conn is not None
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS strategy_actions (
                id TEXT PRIMARY KEY,
                created_at TEXT,
                status TEXT,
                payload_json TEXT,
                decision_id TEXT,
                event_id TEXT
            )
            """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_actions_status ON strategy_actions(status)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_actions_event_id ON strategy_actions(event_id)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_actions_decision_id ON strategy_actions(decision_id)")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS decision_outcomes (
                decision_id TEXT PRIMARY KEY,
                strategy_type TEXT,
                was_autonomous INTEGER,
                predicted_risk REAL,
                revenue_generated REAL DEFAULT 0,
                outcome TEXT,
                evaluated_at TEXT
            )
            """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_decision_outcomes_strategy_type ON decision_outcomes(strategy_type)")
        self._conn.commit()

    def _load_items_from_json(self) -> List[StrategyAction]:
        if not self._path.exists():
            return []
        loaded = atomic_read_json(self._path, [])
        if not isinstance(loaded, list):
            quarantine_corrupt_file(self._path, ValueError("expected list"))
            return []
        return [self._normalize_item(dict(item)) for item in loaded if isinstance(item, dict)]

    def _load_items_from_sqlite(self) -> List[StrategyAction]:
        assert self._conn is not None
        rows = self._conn.execute(
            "SELECT payload_json, decision_id, event_id FROM strategy_actions ORDER BY created_at ASC"
        ).fetchall()
        items: list[StrategyAction] = []
        for payload_json, decision_id, event_id in rows:
            try:
                payload = json.loads(payload_json or "{}")
            except json.JSONDecodeError:
                payload = {}
            if not isinstance(payload, dict):
                payload = {}
            if decision_id and not payload.get("decision_id"):
                payload["decision_id"] = decision_id
            if event_id and not payload.get("event_id"):
                payload["event_id"] = event_id
            items.append(self._normalize_item(payload))
        return items

    def _migrate_json_to_sqlite(self, items: List[StrategyAction]) -> None:
        for item in items:
            self._upsert_sqlite(item)
        if self._conn is not None:
            self._conn.commit()

    def _save_json_legacy(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self._path, list(self._items))

    def _upsert_sqlite(self, item: StrategyAction) -> None:
        if not self._sqlite_enabled or self._conn is None:
            return
        decision_id = str(item.get("decision_id") or "").strip() or None
        event_id = str(item.get("event_id") or "").strip() or None
        self._conn.execute(
            """
            INSERT INTO strategy_actions (id, created_at, status, payload_json, decision_id, event_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                created_at = excluded.created_at,
                status = excluded.status,
                payload_json = excluded.payload_json,
                decision_id = excluded.decision_id,
                event_id = excluded.event_id
            """,
            (
                str(item.get("id") or ""),
                str(item.get("created_at") or self._now()),
                str(item.get("status") or "pending_confirmation"),
                json.dumps(item),
                decision_id,
                event_id,
            ),
        )

    def _predict_risk_for_decision(self, decision_id: str) -> float | None:
        if not self._sqlite_enabled or self._conn is None or not decision_id:
            return None
        try:
            row = self._conn.execute(
                "SELECT risk_score FROM decision_logs WHERE id = ?",
                (decision_id,),
            ).fetchone()
        except sqlite3.Error:
            return None
        if row is None or row[0] is None:
            return None
        try:
            return float(row[0])
        except (TypeError, ValueError):
            return None

    def _record_decision_outcome(self, item: StrategyAction) -> None:
        if not self._sqlite_enabled or self._conn is None:
            return
        decision_id = str(item.get("decision_id") or "").strip()
        if not decision_id:
            return

        status = str(item.get("status") or "").strip().lower()
        strategy_type = str(item.get("type") or "").strip()
        was_autonomous = 1 if status == "auto_executed" else 0
        revenue_generated = float(item.get("revenue_generated", item.get("revenue_delta", 0)) or 0)
        if status == "failed":
            outcome = "failed"
        elif revenue_generated > 0:
            outcome = "success"
        else:
            outcome = "neutral"
        predicted_risk = self._predict_risk_for_decision(decision_id)

        self._conn.execute(
            """
            INSERT INTO decision_outcomes (
                decision_id, strategy_type, was_autonomous, predicted_risk,
                revenue_generated, outcome, evaluated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(decision_id) DO UPDATE SET
                strategy_type = excluded.strategy_type,
                was_autonomous = excluded.was_autonomous,
                predicted_risk = COALESCE(excluded.predicted_risk, decision_outcomes.predicted_risk),
                revenue_generated = excluded.revenue_generated,
                outcome = excluded.outcome,
                evaluated_at = excluded.evaluated_at
            """,
            (
                decision_id,
                strategy_type,
                was_autonomous,
                predicted_risk,
                revenue_generated,
                outcome,
                self._now(),
            ),
        )

    def _persist(self, item: StrategyAction) -> None:
        if self._sqlite_enabled and self._conn is not None:
            self._upsert_sqlite(item)
            if str(item.get("status") or "").strip().lower() in {"executed", "auto_executed", "completed", "failed"}:
                self._record_decision_outcome(item)
            self._conn.commit()
            return
        self._save_json_legacy()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _next_id(self) -> str:
        max_index = 0
        for item in self._items:
            item_id = str(item.get("id", ""))
            if item_id.startswith("action-"):
                try:
                    max_index = max(max_index, int(item_id.replace("action-", "")))
                except ValueError:
                    continue
        return f"action-{max_index + 1:06d}"

    def _normalize_item(self, item: StrategyAction) -> StrategyAction:
        action_type = str(item.get("type") or "review")
        if action_type not in self._ALLOWED_TYPES:
            action_type = "review"

        status = str(item.get("status") or "pending_confirmation")
        if status not in self._ALLOWED_STATUSES:
            status = "pending_confirmation"

        sales = item.get("sales")
        try:
            normalized_sales = max(int(sales), 0) if sales is not None else None
        except (TypeError, ValueError):
            normalized_sales = None

        normalized = {
            "id": str(item.get("id") or self._next_id()),
            "type": action_type,
            "target_id": str(item.get("target_id") or ""),
            "reasoning": str(item.get("reasoning") or ""),
            "status": status,
            "created_at": str(item.get("created_at") or self._now()),
        }
        executed_at = str(item.get("executed_at") or "").strip()
        if executed_at:
            normalized["executed_at"] = executed_at
        if normalized_sales is not None:
            normalized["sales"] = normalized_sales

        decision_id = str(item.get("decision_id") or "").strip()
        event_id = str(item.get("event_id") or "").strip()
        trace_id = str(item.get("trace_id") or "").strip()
        if decision_id:
            normalized["decision_id"] = decision_id
        if event_id:
            normalized["event_id"] = event_id
        if trace_id:
            normalized["trace_id"] = trace_id

        normalized.update(self._risk_evaluation_engine.evaluate(normalized))
        return normalized

    def _find(self, action_id: str) -> StrategyAction | None:
        for item in self._items:
            if item.get("id") == action_id:
                return item
        return None

    def add(
        self,
        *,
        action_type: str,
        target_id: str,
        reasoning: str,
        status: str = "pending_confirmation",
        sales: int | None = None,
        decision_id: str | None = None,
        event_id: str | None = None,
        trace_id: str | None = None,
    ) -> StrategyAction:
        item = self._normalize_item(
            {
                "id": self._next_id(),
                "type": action_type,
                "target_id": target_id,
                "reasoning": reasoning,
                "status": status,
                "created_at": self._now(),
                "sales": sales,
                "decision_id": decision_id,
                "event_id": event_id,
                "trace_id": trace_id,
            }
        )
        self._items.append(item)
        self._persist(item)
        return deepcopy(item)

    def list(self, status: str | None = None) -> List[StrategyAction]:
        items = list(reversed(self._items))
        if status is not None:
            items = [item for item in items if item.get("status") == status]
        return deepcopy(items)

    def get(self, action_id: str) -> StrategyAction | None:
        item = self._find(action_id)
        if item is None:
            return None
        return deepcopy(item)

    def find_pending(self, *, action_type: str, target_id: str, reasoning: str) -> StrategyAction | None:
        for item in reversed(self._items):
            if (
                item.get("type") == action_type
                and item.get("target_id") == target_id
                and item.get("reasoning") == reasoning
                and item.get("status") == "pending_confirmation"
            ):
                return deepcopy(item)
        return None

    def set_status(self, action_id: str, status: str) -> StrategyAction:
        target_status = str(status).strip()
        if target_status not in self._ALLOWED_STATUSES:
            raise ValueError(f"invalid status: {status}")

        item = self._find(action_id)
        if item is None:
            raise ValueError(f"strategy action not found: {action_id}")

        item["status"] = target_status
        if target_status in {"executed", "auto_executed"}:
            item["executed_at"] = self._now()
        self._persist(item)
        return deepcopy(item)
