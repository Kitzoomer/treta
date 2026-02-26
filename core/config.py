import os


STRATEGY_DECISION_COOLDOWN_MINUTES = int(os.getenv("STRATEGY_DECISION_COOLDOWN_MINUTES", "10"))
ACTION_EXECUTION_TIMEOUT_SECONDS = int(os.getenv("ACTION_EXECUTION_TIMEOUT_SECONDS", "300"))
OPENCLAW_BASE_URL = os.getenv("OPENCLAW_BASE_URL", "").strip()
OPENCLAW_TIMEOUT_SECONDS = int(os.getenv("OPENCLAW_TIMEOUT_SECONDS", "5"))
API_TOKEN = os.getenv("TRETA_API_TOKEN")


def get_autonomy_mode() -> str:
    mode = str(os.getenv("AUTONOMY_MODE", "manual")).strip().lower()
    if mode in {"manual", "partial", "disabled"}:
        return mode
    return "manual"
