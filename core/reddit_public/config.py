DEFAULT_CONFIG = {
    "subreddits": [
        "UGCcreators",
        "freelance",
        "ContentCreators",
        "smallbusiness",
    ],
    "pain_threshold": 60,
    "pain_keywords": [
        "struggling",
        "stuck",
        "can't",
        "cannot",
        "problem",
        "issue",
        "need help",
        "confused",
        "overwhelmed",
    ],
    "commercial_keywords": [
        "client",
        "pricing",
        "proposal",
        "media kit",
        "rate",
        "brand deal",
        "charge",
        "template",
    ],
    "enable_engagement_boost": True,
}

_current_config = DEFAULT_CONFIG.copy()


def get_config():
    return _current_config


def update_config(new_config: dict):
    global _current_config
    _current_config.update(new_config)
    return _current_config
