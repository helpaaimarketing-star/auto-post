"""DM outreach helper — generates hyper-personalised DM drafts per lead."""

from typing import Dict

from ai_agent import AIAgent


class DMSender:
    """Generates personalised DM copy for manual Instagram/TikTok/Facebook outreach."""

    def __init__(self):
        self.ai = AIAgent()

    def build_dm(self, lead: Dict, pricing: Dict) -> str:
        return self.ai.generate_dm_script(
            business_name=lead.get("name") or lead.get("BusinessName", ""),
            niche=lead.get("niche") or lead.get("Niche", ""),
            city=lead.get("city") or lead.get("City", ""),
            country=lead.get("country") or lead.get("Country", ""),
            weak_points=lead.get("weak_points") or [],
            pricing=pricing,
            sale_hooks=lead.get("sale_hooks") or [],
            profiles=lead.get("profiles") or {},
        )


__all__ = ["DMSender"]
