import os


STRATEGY_DECISION_COOLDOWN_MINUTES = int(os.getenv("STRATEGY_DECISION_COOLDOWN_MINUTES", "10"))


def get_autonomy_mode() -> str:
    mode = str(os.getenv("AUTONOMY_MODE", "manual")).strip().lower()
    if mode in {"manual", "partial", "disabled"}:
        return mode
    return "manual"
