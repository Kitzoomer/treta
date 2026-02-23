from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from core.creator_intelligence.gumroad_draft import to_gumroad_markdown
from core.creator_intelligence.positioning_engine import CreatorPositioningEngine


class CreatorOfferService:
    def __init__(self, storage):
        self.storage = storage
        self.positioning_engine = CreatorPositioningEngine(storage=storage)

    def generate_offer_draft(self, suggestion_id: str) -> dict:
        self._ensure_schema()
        with self.storage._lock:
            row = self.storage.conn.execute(
                """
                SELECT
                    id,
                    pain_category,
                    frequency,
                    avg_urgency,
                    monetization_level,
                    suggested_product,
                    positioning_angle,
                    estimated_price_range,
                    generated_at
                FROM creator_product_suggestions
                WHERE id = ?
                """,
                (suggestion_id,),
            ).fetchone()
            if row is None:
                raise ValueError("suggestion_not_found")

            suggestion_keys = [
                "id",
                "pain_category",
                "frequency",
                "avg_urgency",
                "monetization_level",
                "suggested_product",
                "positioning_angle",
                "estimated_price_range",
                "generated_at",
            ]
            suggestion = dict(zip(suggestion_keys, row))

            offer = self.positioning_engine.build_offer(suggestion)
            gumroad_description_md = to_gumroad_markdown(offer)
            offer_id = str(uuid.uuid4())
            generated_at = datetime.now(timezone.utc).isoformat()

            draft = {
                "id": offer_id,
                "suggestion_id": suggestion["id"],
                "pain_category": offer["pain_category"],
                "monetization_level": offer["monetization_level"],
                "headline": offer["headline"],
                "subheadline": offer.get("subheadline"),
                "core_promise": offer["core_promise"],
                "who_its_for": offer["who_its_for"],
                "whats_inside": offer["whats_inside"],
                "outcomes": offer["outcomes"],
                "objections": offer["objections"],
                "faq": offer["faq"],
                "price_anchor": offer.get("price_anchor"),
                "suggested_price": offer.get("suggested_price"),
                "gumroad_description_md": gumroad_description_md,
                "generated_at": generated_at,
            }

            self.storage.conn.execute(
                """
                INSERT INTO creator_offer_drafts (
                    id,
                    suggestion_id,
                    pain_category,
                    monetization_level,
                    headline,
                    subheadline,
                    core_promise,
                    who_its_for,
                    whats_inside,
                    outcomes,
                    objections,
                    faq,
                    price_anchor,
                    suggested_price,
                    gumroad_description_md,
                    generated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft["id"],
                    draft["suggestion_id"],
                    draft["pain_category"],
                    draft["monetization_level"],
                    draft["headline"],
                    draft["subheadline"],
                    draft["core_promise"],
                    draft["who_its_for"],
                    json.dumps(draft["whats_inside"]),
                    json.dumps(draft["outcomes"]),
                    json.dumps(draft["objections"]),
                    json.dumps(draft["faq"]),
                    draft["price_anchor"],
                    draft["suggested_price"],
                    draft["gumroad_description_md"],
                    draft["generated_at"],
                ),
            )
            self.storage.conn.commit()
            return draft

    def list_offer_drafts(self, limit=20):
        self._ensure_schema()
        safe_limit = max(1, int(limit))
        with self.storage._lock:
            rows = self.storage.conn.execute(
                """
                SELECT
                    id,
                    suggestion_id,
                    pain_category,
                    monetization_level,
                    headline,
                    subheadline,
                    core_promise,
                    who_its_for,
                    whats_inside,
                    outcomes,
                    objections,
                    faq,
                    price_anchor,
                    suggested_price,
                    gumroad_description_md,
                    generated_at
                FROM creator_offer_drafts
                ORDER BY generated_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()

        return [self._row_to_dict(row) for row in rows]

    def get_offer_draft(self, offer_id: str) -> dict | None:
        self._ensure_schema()
        with self.storage._lock:
            row = self.storage.conn.execute(
                """
                SELECT
                    id,
                    suggestion_id,
                    pain_category,
                    monetization_level,
                    headline,
                    subheadline,
                    core_promise,
                    who_its_for,
                    whats_inside,
                    outcomes,
                    objections,
                    faq,
                    price_anchor,
                    suggested_price,
                    gumroad_description_md,
                    generated_at
                FROM creator_offer_drafts
                WHERE id = ?
                """,
                (offer_id,),
            ).fetchone()

        if row is None:
            return None
        return self._row_to_dict(row)

    def _row_to_dict(self, row) -> dict:
        keys = [
            "id",
            "suggestion_id",
            "pain_category",
            "monetization_level",
            "headline",
            "subheadline",
            "core_promise",
            "who_its_for",
            "whats_inside",
            "outcomes",
            "objections",
            "faq",
            "price_anchor",
            "suggested_price",
            "gumroad_description_md",
            "generated_at",
        ]
        item = dict(zip(keys, row))
        for key in ("whats_inside", "outcomes", "objections", "faq"):
            item[key] = json.loads(item[key]) if item.get(key) else []
        return item

    def _ensure_schema(self):
        self.storage.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS creator_offer_drafts (
                id TEXT PRIMARY KEY,
                suggestion_id TEXT NOT NULL,
                pain_category TEXT NOT NULL,
                monetization_level TEXT NOT NULL,
                headline TEXT NOT NULL,
                subheadline TEXT,
                core_promise TEXT NOT NULL,
                who_its_for TEXT NOT NULL,
                whats_inside TEXT NOT NULL,
                outcomes TEXT NOT NULL,
                objections TEXT NOT NULL,
                faq TEXT NOT NULL,
                price_anchor TEXT,
                suggested_price TEXT,
                gumroad_description_md TEXT NOT NULL,
                generated_at TEXT NOT NULL
            )
            """
        )
