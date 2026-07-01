"""Deal closing, build saving, and email logging to Airtable."""

import logging
from datetime import datetime
from airtable_client import AirtableClient
from utils.helper import generate_order_id

logger = logging.getLogger("OrderManager")


class DealManager:
    """Handles deal closing, build saving, and email logging to Airtable."""

    def __init__(self):
        self.db = AirtableClient()

    def close_deal(self, business_name: str, niche: str, city: str,
                   country: str, package: str, price: int,
                   client_email: str = "", notes: str = "") -> str:
        order_id = generate_order_id(niche, country)
        fields = {
            "OrderID": order_id,
            "BusinessName": business_name,
            "Niche": niche,
            "City": city,
            "Country": country,
            "Package": package,
            "Price": price,
            "ClientEmail": client_email,
            "Status": "Deal Closed",
            "Notes": notes,
            "DealDate": datetime.now().isoformat(),
        }
        try:
            self.db.create("Deals", fields)
            logger.info(f"Deal closed: {order_id} | {business_name} | ${price}/mo")
        except Exception as e:
            logger.error(f"Failed to save deal: {e}")
        return order_id

    def save_build(self, order_id: str, business_name: str, niche: str,
                   platform: str, post_data: dict) -> bool:
        fields = {
            "OrderID": order_id,
            "BusinessName": business_name,
            "Niche": niche,
            "Platform": platform,
            "Caption": post_data.get("caption", ""),
            "Hashtags": post_data.get("hashtags", ""),
            "Description": post_data.get("description", ""),
            "ImagePrompt": post_data.get("image_prompt", ""),
            "CTA": post_data.get("cta", ""),
            "BestTimeToPost": post_data.get("best_time_to_post", ""),
            "EstimatedReach": post_data.get("estimated_reach", ""),
            "Tags": ", ".join(post_data.get("tags", [])) if isinstance(post_data.get("tags"), list) else post_data.get("tags", ""),
            "Status": "Ready for Delivery",
            "BuildDate": datetime.now().isoformat(),
        }
        try:
            self.db.create("Post Builds", fields)
            logger.info(f"Build saved: {order_id} | {platform}")
            return True
        except Exception as e:
            logger.error(f"Failed to save build: {e}")
            return False

    def log_email(self, business_name: str, to_email: str,
                   subject: str, status: str, order_id: str = "") -> None:
        fields = {
            "BusinessName": business_name,
            "ToEmail": to_email,
            "Subject": subject,
            "Status": status,
            "OrderID": order_id,
            "SentAt": datetime.now().isoformat(),
        }
        try:
            self.db.create("Email Log", fields)
        except Exception as e:
            logger.warning(f"Email log failed: {e}")


__all__ = ["DealManager"]
