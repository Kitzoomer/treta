import os


def get_autonomy_mode() -> str:
    mode = str(os.getenv("AUTONOMY_MODE", "manual")).strip().lower()
    if mode in {"manual", "partial", "disabled"}:
        return mode
    return "manual"

