"""Self-learning layer for outcomes, pricing history, and recommendations."""

import logging
from collections import Counter
from datetime import datetime
from typing import Dict, List

from airtable_client import AirtableClient

logger = logging.getLogger("Learner")


class Learner:
    """Tracks what outreach, pricing, and builds perform best."""

    def __init__(self):
        self.db = AirtableClient()

    def record_outcome(self, business_name: str, niche: str, action: str,
                       outcome: str, score: int = 0, notes: str = "") -> bool:
        fields = {
            "BusinessName": business_name,
            "Niche": niche,
            "Action": action,
            "Outcome": outcome,
            "Score": score,
            "Notes": notes,
            "CreatedAt": datetime.now().isoformat(),
        }
        try:
            self.db.create("Learner Data", fields)
            return True
        except Exception as exc:
            logger.warning(f"Learner Data write failed: {exc}")
            return False

    def record_pricing(self, order_id: str, business_name: str, niche: str,
                       package: str, price: int, country: str) -> bool:
        fields = {
            "OrderID": order_id,
            "BusinessName": business_name,
            "Niche": niche,
            "Package": package,
            "Price": price,
            "Country": country,
            "CreatedAt": datetime.now().isoformat(),
        }
        try:
            self.db.create("Pricing History", fields)
            return True
        except Exception as exc:
            logger.warning(f"Pricing History write failed: {exc}")
            return False

    def summarize(self, niche: str = "") -> Dict:
        formula = f"{{Niche}}='{niche}'" if niche else None
        try:
            records = self.db.fetch_all("Learner Data", formula=formula)
        except Exception as exc:
            logger.warning(f"Learner summary failed: {exc}")
            return {"total": 0, "best_actions": [], "top_outcomes": []}

        actions: List[str] = []
        outcomes: List[str] = []
        for record in records:
            fields = record.get("fields", {})
            if fields.get("Action"):
                actions.append(fields["Action"])
            if fields.get("Outcome"):
                outcomes.append(fields["Outcome"])
        return {
            "total": len(records),
            "best_actions": Counter(actions).most_common(5),
            "top_outcomes": Counter(outcomes).most_common(5),
        }


__all__ = ["Learner"]
