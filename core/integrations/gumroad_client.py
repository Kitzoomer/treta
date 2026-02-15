from __future__ import annotations

from typing import Any

try:
    import requests
except ModuleNotFoundError:  # pragma: no cover
    class _RequestsShim:
        @staticmethod
        def get(url: str, params: dict[str, str], timeout: int):
            return _fallback_get(url, params=params, timeout=timeout)

    requests = _RequestsShim()




class _FallbackResponse:
    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> Any:
        return self._payload


def _fallback_get(url: str, params: dict[str, str], timeout: int) -> _FallbackResponse:
    from urllib.parse import urlencode
    from urllib.request import urlopen
    import json as _json

    query = urlencode(params)
    with urlopen(f"{url}?{query}", timeout=timeout) as resp:
        body = _json.loads(resp.read().decode("utf-8"))
        return _FallbackResponse(resp.status, body)


class GumroadAPIError(RuntimeError):
    """Raised when Gumroad API communication fails."""


class GumroadClient:
    """Minimal Gumroad sales client."""

    _SALES_ENDPOINT = "https://api.gumroad.com/v2/sales"

    def __init__(self, access_token: str) -> None:
        token = str(access_token or "").strip()
        if not token:
            raise ValueError("Missing Gumroad access token. Set GUMROAD_ACCESS_TOKEN.")
        self._access_token = token

    def get_sales(self, product_id: str, after: str | None = None) -> list[dict[str, Any]]:
        normalized_product_id = str(product_id or "").strip()
        if not normalized_product_id:
            raise ValueError("missing_product_id")

        params: dict[str, str] = {
            "access_token": self._access_token,
            "product_id": normalized_product_id,
        }
        if after:
            params["after"] = str(after)

        try:
            response = requests.get(self._SALES_ENDPOINT, params=params, timeout=10)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # requests/network/json failures
            raise GumroadAPIError(f"Gumroad API request failed: {exc}") from exc

        sales = payload.get("sales", []) if isinstance(payload, dict) else []
        if not isinstance(sales, list):
            raise GumroadAPIError("Gumroad API returned invalid sales payload.")

        normalized: list[dict[str, Any]] = []
        for sale in sales:
            if not isinstance(sale, dict):
                continue
            sale_id = str(sale.get("id") or "").strip()
            if not sale_id:
                continue

            amount_raw = sale.get("price")
            if amount_raw is None:
                amount_raw = sale.get("amount")
            if amount_raw is None:
                amount_raw = sale.get("amount_cents")

            try:
                amount = float(amount_raw)
            except (TypeError, ValueError):
                amount = 0.0

            if "amount_cents" in sale:
                amount = amount / 100.0

            created_at = sale.get("created_at")
            normalized.append(
                {
                    "sale_id": sale_id,
                    "amount": round(amount, 2),
                    "created_at": str(created_at or ""),
                }
            )

        return normalized
