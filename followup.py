"""Interest tracking and follow-up scheduling."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List

from airtable_client import AirtableClient

logger = logging.getLogger("FollowUpManager")


class FollowUpManager:
    """Stores and retrieves follow-up tasks from Airtable."""

    def __init__(self):
        self.db = AirtableClient()

    def create_followup(self, business_name: str, contact: str, channel: str,
                        interest_level: str, notes: str = "",
                        due_days: int = 2, order_id: str = "") -> bool:
        due_at = (datetime.now() + timedelta(days=max(0, due_days))).date().isoformat()
        fields = {
            "BusinessName": business_name,
            "Contact": contact,
            "Channel": channel,
            "InterestLevel": interest_level,
            "Notes": notes,
            "OrderID": order_id,
            "Status": "Open",
            "DueAt": due_at,
            "CreatedAt": datetime.now().isoformat(),
        }
        try:
            self.db.create("Follow-ups", fields)
            return True
        except Exception as exc:
            logger.warning(f"Follow-up create failed: {exc}")
            return False

    def list_open(self, limit: int = 10) -> List[Dict]:
        try:
            records = self.db.fetch_all(
                "Follow-ups",
                formula="{Status}='Open'",
                sort=[{"field": "DueAt", "direction": "asc"}],
            )
            return records[:limit]
        except Exception as exc:
            logger.warning(f"Follow-up list failed: {exc}")
            return []


__all__ = ["FollowUpManager"]
