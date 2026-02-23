from __future__ import annotations

import uuid
from datetime import datetime, timezone


class CreatorLaunchTracker:
    def __init__(self, storage):
        self.storage = storage

    def register_launch(self, offer_id: str, price: float, notes: str = ""):
        self._ensure_schema()
        with self.storage._lock:
            offer = self.storage.conn.execute(
                """
                SELECT id, pain_category, monetization_level
                FROM creator_offer_drafts
                WHERE id = ?
                """,
                (offer_id,),
            ).fetchone()
            if offer is None:
                raise ValueError("offer_not_found")

            now = datetime.now(timezone.utc).isoformat()
            launch = {
                "id": str(uuid.uuid4()),
                "offer_id": str(offer[0]),
                "pain_category": str(offer[1]),
                "monetization_level": str(offer[2]),
                "launch_date": now,
                "price": float(price),
                "sales": 0,
                "revenue": 0.0,
                "notes": notes or "",
                "created_at": now,
                "updated_at": now,
            }

            self.storage.conn.execute(
                """
                INSERT INTO creator_offer_launches (
                    id,
                    offer_id,
                    pain_category,
                    monetization_level,
                    launch_date,
                    price,
                    sales,
                    revenue,
                    notes,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    launch["id"],
                    launch["offer_id"],
                    launch["pain_category"],
                    launch["monetization_level"],
                    launch["launch_date"],
                    launch["price"],
                    launch["sales"],
                    launch["revenue"],
                    launch["notes"],
                    launch["created_at"],
                    launch["updated_at"],
                ),
            )
            self.storage.conn.commit()
        return launch

    def record_sale(self, launch_id: str, quantity: int = 1):
        self._ensure_schema()
        quantity = int(quantity)
        if quantity < 1:
            raise ValueError("invalid_quantity")

        with self.storage._lock:
            row = self.storage.conn.execute(
                """
                SELECT id, price, sales, revenue
                FROM creator_offer_launches
                WHERE id = ?
                """,
                (launch_id,),
            ).fetchone()
            if row is None:
                raise ValueError("launch_not_found")

            current_sales = int(row[2] or 0)
            current_revenue = float(row[3] or 0.0)
            price = float(row[1])
            updated_sales = current_sales + quantity
            updated_revenue = current_revenue + (price * quantity)
            updated_at = datetime.now(timezone.utc).isoformat()

            self.storage.conn.execute(
                """
                UPDATE creator_offer_launches
                SET sales = ?, revenue = ?, updated_at = ?
                WHERE id = ?
                """,
                (updated_sales, updated_revenue, updated_at, launch_id),
            )
            row = self.storage.conn.execute(
                """
                SELECT
                    id,
                    offer_id,
                    pain_category,
                    monetization_level,
                    launch_date,
                    price,
                    sales,
                    revenue,
                    notes,
                    created_at,
                    updated_at
                FROM creator_offer_launches
                WHERE id = ?
                """,
                (launch_id,),
            ).fetchone()
            self.storage.conn.commit()

            return self._row_to_dict(row)

    def list_launches(self, limit: int = 50):
        self._ensure_schema()
        safe_limit = max(1, int(limit))
        with self.storage._lock:
            rows = self.storage.conn.execute(
                """
                SELECT
                    id,
                    offer_id,
                    pain_category,
                    monetization_level,
                    launch_date,
                    price,
                    sales,
                    revenue,
                    notes,
                    created_at,
                    updated_at
                FROM creator_offer_launches
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_launch(self, launch_id: str):
        self._ensure_schema()
        with self.storage._lock:
            row = self.storage.conn.execute(
                """
                SELECT
                    id,
                    offer_id,
                    pain_category,
                    monetization_level,
                    launch_date,
                    price,
                    sales,
                    revenue,
                    notes,
                    created_at,
                    updated_at
                FROM creator_offer_launches
                WHERE id = ?
                """,
                (launch_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def get_performance_summary(self):
        self._ensure_schema()
        with self.storage._lock:
            rows = self.storage.conn.execute(
                """
                SELECT
                    pain_category,
                    SUM(COALESCE(sales, 0)) AS total_sales,
                    SUM(COALESCE(revenue, 0)) AS total_revenue,
                    AVG(price) AS avg_price
                FROM creator_offer_launches
                GROUP BY pain_category
                ORDER BY total_revenue DESC
                """
            ).fetchall()

        categories = []
        top_category_by_revenue = None
        for row in rows:
            item = {
                "pain_category": str(row[0]),
                "total_sales": int(row[1] or 0),
                "total_revenue": float(row[2] or 0.0),
                "avg_price": float(row[3] or 0.0),
            }
            categories.append(item)
            if top_category_by_revenue is None:
                top_category_by_revenue = item["pain_category"]

        return {
            "categories": categories,
            "top_category_by_revenue": top_category_by_revenue,
        }

    def _row_to_dict(self, row):
        keys = [
            "id",
            "offer_id",
            "pain_category",
            "monetization_level",
            "launch_date",
            "price",
            "sales",
            "revenue",
            "notes",
            "created_at",
            "updated_at",
        ]
        data = dict(zip(keys, row))
        data["price"] = float(data["price"])
        data["sales"] = int(data["sales"] or 0)
        data["revenue"] = float(data["revenue"] or 0.0)
        return data

    def _ensure_schema(self):
        self.storage.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS creator_offer_launches (
              id TEXT PRIMARY KEY,
              offer_id TEXT NOT NULL,
              pain_category TEXT NOT NULL,
              monetization_level TEXT NOT NULL,
              launch_date TEXT NOT NULL,
              price REAL NOT NULL,
              sales INTEGER DEFAULT 0,
              revenue REAL DEFAULT 0,
              notes TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
