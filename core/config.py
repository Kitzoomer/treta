import os


def _apply_ci_auth_defaults() -> bool:
    if os.getenv("CI") != "true":
        return False
    if "TRETA_DEV_MODE" in os.environ or "TRETA_REQUIRE_TOKEN" in os.environ:
        return False
    os.environ["TRETA_DEV_MODE"] = "1"
    os.environ["TRETA_REQUIRE_TOKEN"] = "0"
    return True


CI_AUTH_AUTO_DETECTED = _apply_ci_auth_defaults()


STRATEGY_DECISION_COOLDOWN_MINUTES = int(os.getenv("STRATEGY_DECISION_COOLDOWN_MINUTES", "10"))
ACTION_EXECUTION_TIMEOUT_SECONDS = int(os.getenv("ACTION_EXECUTION_TIMEOUT_SECONDS", "300"))
ACTION_APPROVAL_MIN_RISK_LEVEL = str(os.getenv("ACTION_APPROVAL_MIN_RISK_LEVEL", "high")).strip().lower()
ACTION_CIRCUIT_BREAKER_FAILURE_THRESHOLD = int(os.getenv("ACTION_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "2"))
ACTION_CIRCUIT_BREAKER_WINDOW_SECONDS = int(os.getenv("ACTION_CIRCUIT_BREAKER_WINDOW_SECONDS", "600"))
OPENCLAW_BASE_URL = os.getenv("OPENCLAW_BASE_URL", "").strip()
OPENCLAW_TIMEOUT_SECONDS = int(os.getenv("OPENCLAW_TIMEOUT_SECONDS", "5"))
API_TOKEN = os.getenv("TRETA_API_TOKEN")
TRETA_DEV_MODE = str(os.getenv("TRETA_DEV_MODE", "0")).strip() == "1"
TRETA_REQUIRE_TOKEN = str(os.getenv("TRETA_REQUIRE_TOKEN", "1")).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
STRATEGY_LOOP_ENABLED = str(os.getenv("STRATEGY_LOOP_ENABLED", "true")).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
STRATEGY_LOOP_INTERVAL_SECONDS = float(os.getenv("STRATEGY_LOOP_INTERVAL_SECONDS", "900"))
STRATEGY_LOOP_MAX_PENDING = int(os.getenv("STRATEGY_LOOP_MAX_PENDING", "5"))
MAX_REQUEST_BODY_BYTES = int(os.getenv("TRETA_MAX_REQUEST_BODY_BYTES", str(1024 * 1024)))


def get_autonomy_mode() -> str:
    mode = str(os.getenv("AUTONOMY_MODE", "manual")).strip().lower()
    if mode in {"manual", "partial", "disabled"}:
        return mode
    return "manual"
