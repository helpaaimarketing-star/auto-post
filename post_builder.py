"""Text and image-prompt post package builder."""

from typing import Dict

from order_manager import DealManager
from output.post_processor import build_post_text_file
from ai_agent import AIAgent


class PostBuilder:
    """Builds a complete client deliverable for an order."""

    def __init__(self):
        self.ai = AIAgent()
        self.deals = DealManager()

    def build_package(self, order_id: str, business_name: str, niche: str,
                      city: str, platform: str = "instagram") -> Dict:
        post_data = self.ai.generate_social_post(
            business_name, niche, city, order_id, platform)
        self.deals.save_build(order_id, business_name, niche, platform, post_data)
        text_file = build_post_text_file(post_data, business_name, niche, order_id, platform)
        return {"post_data": post_data, "text_file": text_file}


__all__ = ["PostBuilder"]
