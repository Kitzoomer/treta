"""Gumroad integration client.

This module intentionally avoids direct HTTP concerns. Network behavior must be
provided by the injected ``transport`` object.
"""

from __future__ import annotations

import os
from typing import Any, Optional


class GumroadClient:
    """Small Gumroad API client with OAuth token flow.

    The ``transport`` dependency is expected to provide:
    - ``oauth_token(app_id: str, app_secret: str) -> str``
    - ``get(path: str, access_token: str) -> dict[str, Any]``
    """

    def __init__(
        self,
        transport: Any,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
    ) -> None:
        self._transport = transport
        self._app_id = app_id if app_id is not None else os.getenv("GUMROAD_APP_ID")
        self._app_secret = (
            app_secret if app_secret is not None else os.getenv("GUMROAD_APP_SECRET")
        )
        self._access_token: Optional[str] = None

    def _has_credentials(self) -> bool:
        return bool(self._app_id and self._app_secret)

    def _get_access_token(self) -> Optional[str]:
        if self._access_token:
            return self._access_token

        if not self._has_credentials():
            return None

        try:
            self._access_token = self._transport.oauth_token(
                app_id=self._app_id,
                app_secret=self._app_secret,
            )
        except Exception:
            return None

        return self._access_token

    def _safe_get(self, path: str) -> dict[str, Any]:
        token = self._get_access_token()
        if not token:
            return {}

        try:
            response = self._transport.get(path=path, access_token=token)
        except Exception:
            return {}

        if not isinstance(response, dict):
            return {}
        return response

    def get_products(self) -> list[dict[str, Any]]:
        """Fetch products from Gumroad API."""
        payload = self._safe_get("/v2/products")
        products = payload.get("products", [])
        return products if isinstance(products, list) else []

    def get_sales(self) -> list[dict[str, Any]]:
        """Fetch sales from Gumroad API."""
        payload = self._safe_get("/v2/sales")
        sales = payload.get("sales", [])
        return sales if isinstance(sales, list) else []

    def get_balance(self) -> dict[str, Any]:
        """Fetch account balance information from Gumroad API."""
        payload = self._safe_get("/v2/balance")
        if not payload:
            return {}

        balance = payload.get("balance")
        if isinstance(balance, dict):
            return balance

        return payload if isinstance(payload, dict) else {}
