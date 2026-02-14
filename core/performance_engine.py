from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict

from core.product_launch_store import ProductLaunchStore


class PerformanceEngine:
    """Aggregates launch metrics into business-level insights."""

    def __init__(self, product_launch_store: ProductLaunchStore):
        self._product_launch_store = product_launch_store

    def _launches(self) -> list[Dict[str, Any]]:
        return self._product_launch_store.list()

    def total_revenue(self) -> float:
        return round(
            sum(float(item.get("metrics", {}).get("revenue", 0.0) or 0.0) for item in self._launches()),
            2,
        )

    def total_sales(self) -> int:
        return int(sum(int(item.get("metrics", {}).get("sales", 0) or 0) for item in self._launches()))

    def revenue_by_product(self) -> Dict[str, float]:
        totals: dict[str, float] = defaultdict(float)
        for item in self._launches():
            name = str(item.get("product_name") or "unknown")
            revenue = float(item.get("metrics", {}).get("revenue", 0.0) or 0.0)
            totals[name] += revenue
        return {name: round(amount, 2) for name, amount in totals.items()}

    def best_performing_product(self) -> str | None:
        by_product = self.revenue_by_product()
        if not by_product:
            return None
        return max(sorted(by_product), key=lambda name: by_product[name])

    def _product_type_for_name(self, product_name: str) -> str:
        tokens = [token.lower() for token in product_name.replace("+", " ").split() if token.isalpha()]
        if not tokens:
            return "unknown"
        return tokens[-1]

    def revenue_by_product_type(self) -> Dict[str, float]:
        totals: dict[str, float] = defaultdict(float)
        for item in self._launches():
            product_name = str(item.get("product_name") or "unknown")
            product_type = self._product_type_for_name(product_name)
            revenue = float(item.get("metrics", {}).get("revenue", 0.0) or 0.0)
            totals[product_type] += revenue
        return {name: round(amount, 2) for name, amount in totals.items()}

    def generate_insights(self) -> Dict[str, Any]:
        revenue_by_type = self.revenue_by_product_type()
        top_category = max(sorted(revenue_by_type), key=lambda name: revenue_by_type[name]) if revenue_by_type else None
        best_product = self.best_performing_product()

        recommendation = "Collect more sales data before making pricing recommendations."
        if top_category is not None:
            suffix = "s" if not top_category.endswith("s") else ""
            recommendation = f"Double down on creator-focused {top_category}{suffix} priced under $30."

        return {
            "total_revenue": self.total_revenue(),
            "total_sales": self.total_sales(),
            "best_product": best_product,
            "top_category": top_category,
            "recommendation": recommendation,
        }
