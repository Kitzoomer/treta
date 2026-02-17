import sqlite3

import pytest

from core.reddit_intelligence.models import get_db_path, initialize_sqlite
from core.reddit_intelligence.service import RedditIntelligenceService


@pytest.fixture(autouse=True)
def reddit_db(tmp_path, monkeypatch):
    monkeypatch.setenv("TRETA_DATA_DIR", str(tmp_path))
    initialize_sqlite()
    yield
    db_path = get_db_path()
    if db_path.exists():
        db_path.unlink()


def _new_service() -> RedditIntelligenceService:
    return RedditIntelligenceService()


def test_analyze_post_direct_classification():
    service = _new_service()

    signal = service.analyze_post(
        subreddit="freelance",
        post_text="Does anyone have a template for a media kit?",
        post_url="https://reddit.com/r/freelance/direct-1",
    )

    assert signal["intent_level"] == "direct"
    assert signal["suggested_action"] == "value_plus_mention"
    assert signal["opportunity_score"] >= 80


def test_analyze_post_implicit_classification():
    service = _new_service()

    signal = service.analyze_post(
        subreddit="creators",
        post_text="I'm struggling to close brand deals",
        post_url="https://reddit.com/r/creators/implicit-1",
    )

    assert signal["intent_level"] == "implicit"
    assert signal["suggested_action"] == "value"
    assert 50 <= signal["opportunity_score"] <= 75


def test_analyze_post_trend_classification():
    service = _new_service()

    signal = service.analyze_post(
        subreddit="creators",
        post_text="Interesting discussion about creators",
        post_url="https://reddit.com/r/creators/trend-1",
    )

    assert signal["intent_level"] == "trend"
    assert signal["suggested_action"] == "ignore"


def test_analyze_post_persists_signal_in_sqlite():
    service = _new_service()

    signal = service.analyze_post(
        subreddit="startups",
        post_text="Need help choosing a pricing model",
        post_url="https://reddit.com/r/startups/persist-1",
    )

    conn = sqlite3.connect(get_db_path())
    try:
        row = conn.execute(
            "SELECT id, subreddit, status FROM reddit_signals WHERE id = ?",
            (signal["id"],),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row[0] == signal["id"]
    assert row[1] == "startups"
    assert row[2] == "pending"


def test_list_top_pending_orders_by_score_desc():
    service = _new_service()

    low = service.analyze_post(
        subreddit="entrepreneur",
        post_text="Interesting discussion about creators",
        post_url="https://reddit.com/r/entrepreneur/low",
    )
    medium = service.analyze_post(
        subreddit="entrepreneur",
        post_text="I'm struggling to close brand deals",
        post_url="https://reddit.com/r/entrepreneur/medium",
    )
    high = service.analyze_post(
        subreddit="entrepreneur",
        post_text="Does anyone have a template for a media kit?",
        post_url="https://reddit.com/r/entrepreneur/high",
    )

    ordered = service.list_top_pending(limit=3)

    assert [item["id"] for item in ordered] == [high["id"], medium["id"], low["id"]]
    assert [item["opportunity_score"] for item in ordered] == sorted(
        [low["opportunity_score"], medium["opportunity_score"], high["opportunity_score"]],
        reverse=True,
    )


def test_update_status_changes_signal_status():
    service = _new_service()

    signal = service.analyze_post(
        subreddit="saas",
        post_text="Need help with a sales template",
        post_url="https://reddit.com/r/saas/update-1",
    )

    updated = service.update_status(signal_id=signal["id"], status="approved")

    assert updated is not None
    assert updated["id"] == signal["id"]
    assert updated["status"] == "approved"
