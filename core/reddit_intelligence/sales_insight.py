from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List


class SalesInsightService:
    def get_high_performing_keywords(self) -> List[str]:
        try:
            from core.product_launch_store import ProductLaunchStore
            from core.product_proposal_store import ProductProposalStore
        except Exception:
            return []

        try:
            proposal_store = ProductProposalStore()
            launch_store = ProductLaunchStore(proposal_store=proposal_store)
            launches = launch_store.list()
            proposals = proposal_store.list()
        except Exception:
            return []

        proposal_by_id = {
            str(item.get("id")): item
            for item in proposals
            if isinstance(item, dict) and item.get("id") is not None
        }

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=30)
        keywords: set[str] = set()

        for launch in launches:
            if not isinstance(launch, dict):
                continue

            sales = int(launch.get("metrics", {}).get("sales", 0) or 0)
            if sales < 3:
                continue

            created_at = str(launch.get("created_at") or "").strip()
            if created_at:
                try:
                    created_dt = datetime.fromisoformat(created_at)
                    if created_dt.tzinfo is None:
                        created_dt = created_dt.replace(tzinfo=timezone.utc)
                    if created_dt < cutoff:
                        continue
                except ValueError:
                    pass

            proposal = proposal_by_id.get(str(launch.get("proposal_id") or ""), {})
            for field_value in (
                launch.get("product_name"),
                proposal.get("product_name"),
                proposal.get("core_problem"),
                proposal.get("target_audience"),
            ):
                for token in self._extract_keywords(field_value):
                    keywords.add(token)

        return sorted(keywords)

    def _extract_keywords(self, value: object) -> List[str]:
        text = str(value or "").lower().strip()
        if not text:
            return []

        cleaned = "".join(ch if ch.isalnum() else " " for ch in text)
        tokens = [part for part in cleaned.split() if len(part) >= 3]
        return tokens
