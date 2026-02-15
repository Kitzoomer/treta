import json
import os
from pathlib import Path
from urllib.parse import urlencode

try:
    import requests
except ModuleNotFoundError:  # pragma: no cover
    class _RequestsShim:
        @staticmethod
        def post(url: str, data: dict[str, str], timeout: int):
            return _fallback_post(url, data=data, timeout=timeout)

    requests = _RequestsShim()


class _FallbackResponse:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def _fallback_post(url: str, data: dict[str, str], timeout: int) -> _FallbackResponse:
    import json as _json
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen

    encoded = urlencode(data).encode("utf-8")
    request = Request(url, data=encoded, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urlopen(request, timeout=timeout) as resp:
        body = _json.loads(resp.read().decode("utf-8"))
        return _FallbackResponse(resp.status, body)


_AUTH_BASE_URL = "https://gumroad.com/oauth/authorize"
_TOKEN_URL = "https://api.gumroad.com/oauth/token"
_TOKEN_FILE_NAME = "gumroad_oauth_token.json"


def _data_dir() -> Path:
    return Path(os.getenv("TRETA_DATA_DIR", "/data")).resolve()


def _token_path() -> Path:
    return _data_dir() / _TOKEN_FILE_NAME


def get_auth_url() -> str:
    app_id = str(os.getenv("GUMROAD_CLIENT_ID") or os.getenv("GUMROAD_APP_ID") or "").strip()
    redirect_uri = str(os.getenv("GUMROAD_REDIRECT_URI") or "").strip()
    if not app_id or not redirect_uri:
        raise ValueError(
            "Missing Gumroad OAuth configuration. Set GUMROAD_CLIENT_ID (or GUMROAD_APP_ID) and GUMROAD_REDIRECT_URI."
        )

    query = urlencode(
        {
            "client_id": app_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
        }
    )
    return f"{_AUTH_BASE_URL}?{query}"


def exchange_code_for_token(code: str) -> str:
    normalized_code = str(code or "").strip()
    if not normalized_code:
        raise ValueError("missing_code")

    app_id = str(os.getenv("GUMROAD_CLIENT_ID") or os.getenv("GUMROAD_APP_ID") or "").strip()
    app_secret = str(os.getenv("GUMROAD_CLIENT_SECRET") or os.getenv("GUMROAD_APP_SECRET") or "").strip()
    redirect_uri = str(os.getenv("GUMROAD_REDIRECT_URI") or "").strip()
    if not app_id or not app_secret or not redirect_uri:
        raise ValueError(
            "Missing Gumroad OAuth configuration. Set GUMROAD_CLIENT_ID/GUMROAD_CLIENT_SECRET "
            "(or GUMROAD_APP_ID/GUMROAD_APP_SECRET) and GUMROAD_REDIRECT_URI."
        )

    response = requests.post(
        _TOKEN_URL,
        data={
            "client_id": app_id,
            "client_secret": app_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "code": normalized_code,
        },
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    token = str(payload.get("access_token") or "").strip() if isinstance(payload, dict) else ""
    if not token:
        raise ValueError("missing_access_token")
    return token


def save_token(token: str) -> None:
    normalized_token = str(token or "").strip()
    if not normalized_token:
        raise ValueError("missing_access_token")

    path = _token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"access_token": normalized_token}, indent=2), encoding="utf-8")


def load_token() -> str | None:
    path = _token_path()
    if not path.exists():
        return None

    payload = json.loads(path.read_text(encoding="utf-8"))
    token = str(payload.get("access_token") or "").strip() if isinstance(payload, dict) else ""
    return token or None
