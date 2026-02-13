"""Gumroad integration client.

This module intentionally avoids direct HTTP concerns. Network behavior must be
provided by the injected ``transport`` object.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)


class GumroadClient:
    """Small Gumroad API client with OAuth token flow.

    The ``transport`` dependency is expected to provide:
    - ``oauth_token(app_id: str, app_secret: str) -> str``
    - ``get(path: str, access_token: str, params: dict[str, Any] | None = None) -> dict[str, Any]``
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
        self._missing_credentials_logged = False

    def _has_credentials(self) -> bool:
        return bool(self._app_id and self._app_secret)

    def _warn_missing_credentials(self) -> None:
        if self._missing_credentials_logged:
            return
        logger.warning(
            "Gumroad credentials are missing; returning empty integration payloads."
        )
        self._missing_credentials_logged = True

    def _get_access_token(self) -> Optional[str]:
        if self._access_token:
            return self._access_token

        if not self._has_credentials():
            self._warn_missing_credentials()
            return None

        try:
            self._access_token = self._transport.oauth_token(
                app_id=self._app_id,
                app_secret=self._app_secret,
            )
        except Exception:
            logger.warning("Gumroad OAuth token fetch failed.", exc_info=True)
            return None

        return self._access_token

    def _safe_get(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        token = self._get_access_token()
        if not token:
            return {}

        try:
            response = self._transport.get(
                path=path,
                access_token=token,
                params=params,
            )
        except TypeError:
            try:
                response = self._transport.get(path=path, access_token=token)
            except Exception:
                logger.warning("Gumroad API request failed for path '%s'.", path, exc_info=True)
                return {}
        except Exception:
            logger.warning("Gumroad API request failed for path '%s'.", path, exc_info=True)
            return {}

        if not isinstance(response, dict):
            return {}
        return response

    @staticmethod
    def _empty_products_payload() -> dict[str, list[dict[str, Any]]]:
        return {"products": []}

    @staticmethod
    def _empty_sales_payload(limit: int) -> dict[str, Any]:
        return {"sales": [], "limit": limit}

    @staticmethod
    def _empty_revenue_payload() -> dict[str, Any]:
        return {"total_revenue": 0.0, "currency": "USD", "sales_count": 0}

    def get_products(self) -> dict[str, list[dict[str, Any]]]:
        """Fetch products from Gumroad API."""
        payload = self._safe_get("/v2/products")
        if not payload:
            return self._empty_products_payload()

        products = payload.get("products", [])
        if not isinstance(products, list):
            return self._empty_products_payload()

        return {"products": products}

    def get_sales(self, limit: int = 10) -> dict[str, Any]:
        """Fetch sales from Gumroad API."""
        safe_limit = limit if isinstance(limit, int) and limit > 0 else 10
        payload = self._safe_get("/v2/sales", params={"limit": safe_limit})
        if not payload:
            return self._empty_sales_payload(safe_limit)

        sales = payload.get("sales", [])
        if not isinstance(sales, list):
            return self._empty_sales_payload(safe_limit)

        return {"sales": sales[:safe_limit], "limit": safe_limit}

    def get_total_revenue(self) -> dict[str, Any]:
        """Aggregate total revenue from Gumroad sales data."""
        sales_payload = self.get_sales(limit=200)
        sales = sales_payload.get("sales", [])
        if not isinstance(sales, list):
            return self._empty_revenue_payload()

        total_revenue = 0.0
        for sale in sales:
            if not isinstance(sale, dict):
                continue
            raw_amount = sale.get("price")
            if raw_amount is None:
                raw_amount = sale.get("amount_cents")
            try:
                if raw_amount is None:
                    continue
                amount = float(raw_amount)
            except (TypeError, ValueError):
                continue

            if amount > 1000:
                amount = amount / 100.0
            total_revenue += amount

        return {
            "total_revenue": round(total_revenue, 2),
            "currency": "USD",
            "sales_count": len(sales),
        }
