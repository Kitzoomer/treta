from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    conn.execute(
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
    conn.commit()
