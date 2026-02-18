from __future__ import annotations

from typing import Dict

EXPLICIT_PAIN_KEYWORDS = [
    "struggling",
    "stuck",
    "can't",
    "cannot",
    "problem",
    "issue",
    "need help",
    "confused",
    "overwhelmed",
]

COMMERCIAL_INTENT_KEYWORDS = [
    "client",
    "pricing",
    "proposal",
    "media kit",
    "rate",
    "brand deal",
    "charge",
    "template",
]

QUESTION_PATTERNS = [
    "how do i",
    "any advice",
    "what should i",
]

HIGH_URGENCY_KEYWORDS = [
    "urgent",
    "asap",
    "today",
]


def compute_pain_score(post: dict) -> Dict[str, object]:
    title = str(post.get("title", ""))
    body = str(post.get("selftext", ""))
    text = f"{title} {body}".lower()

    score = 0
    has_help = False
    has_commercial = False

    for keyword in EXPLICIT_PAIN_KEYWORDS:
        if keyword in text:
            score += 20
            has_help = True

    for keyword in COMMERCIAL_INTENT_KEYWORDS:
        if keyword in text:
            score += 25
            has_commercial = True

    if title.strip().endswith("?") or any(pattern in text for pattern in QUESTION_PATTERNS):
        score += 15

    num_comments = int(post.get("num_comments", 0) or 0)
    if num_comments >= 15:
        score += 20
    elif num_comments >= 5:
        score += 10

    pain_score = min(score, 100)

    if has_commercial:
        intent_type = "monetization"
    elif has_help:
        intent_type = "pain_help"
    else:
        intent_type = "general"

    if any(keyword in text for keyword in HIGH_URGENCY_KEYWORDS):
        urgency_level = "high"
    elif pain_score >= 70:
        urgency_level = "medium"
    else:
        urgency_level = "low"

    return {
        "pain_score": pain_score,
        "intent_type": intent_type,
        "urgency_level": urgency_level,
    }
