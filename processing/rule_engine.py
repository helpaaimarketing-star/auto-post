"""Business rules — pricing, lead qualification, market logic."""

from typing import Dict, List
from config import Config

INACTIVE_DAYS = 30
MIN_WEAKNESS_SCORE = 4

PREMIUM_COUNTRIES = {
    "United Kingdom", "Germany", "Switzerland",
    "Norway", "Denmark", "Sweden", "Finland",
}


class RuleEngine:
    """Executes business logic based on defined rules."""

    @staticmethod
    def suggest_pricing(niche: str, weak_points: list, country: str) -> Dict:
        niche_key = niche.lower().split()[0]
        pricing = Config.PRICING_TABLE.get(niche_key, Config.PRICING_TABLE["default"])

        if country in PREMIUM_COUNTRIES:
            pricing = {k: int(v * 1.2) for k, v in pricing.items()}

        currency = "GBP" if country == "United Kingdom" else "USD"
        symbol = "£" if country == "United Kingdom" else "$"

        return {
            "starter": pricing["starter"],
            "growth": pricing["growth"],
            "pro": pricing["pro"],
            "recommended": pricing["growth"],
            "currency": currency,
            "symbol": symbol,
            "pitch": f"{symbol}{pricing['starter']}–{symbol}{pricing['growth']}/month",
        }

    @staticmethod
    def calculate_weakness_score(inactive_count: int, weak_points: List[str]) -> int:
        return min(10, inactive_count * 3 + len(weak_points))

    @staticmethod
    def is_qualified_lead(weakness_score: int) -> bool:
        return weakness_score >= MIN_WEAKNESS_SCORE

    @staticmethod
    def is_platform_inactive(days_since_post: int) -> bool:
        return days_since_post > INACTIVE_DAYS
