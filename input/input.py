"""Raw input normalization — converts Discord interactions to structured dicts."""

from typing import Optional, Dict, Any


def normalize_scrape_input(query: str, niche: str, city: Optional[str],
                           country: Optional[str], limit: Optional[int] = 15) -> Dict[str, Any]:
    return {
        "type": "scrape",
        "query": query.strip(),
        "niche": niche.strip(),
        "city": city.strip() if city else None,
        "country": country.strip() if country else None,
        "limit": min(limit or 15, 25),
    }


def normalize_deal_input(business: str, niche: str, city: str, country: str,
                         package: str, price: int,
                         email: Optional[str] = "") -> Dict[str, Any]:
    return {
        "type": "deal_close",
        "business": business.strip(),
        "niche": niche.strip(),
        "city": city.strip(),
        "country": country.strip(),
        "package": package.lower().strip(),
        "price": price,
        "email": (email or "").strip(),
    }


def normalize_build_input(order_id: str, platform: str = "instagram") -> Dict[str, Any]:
    return {
        "type": "build",
        "order_id": order_id.strip().upper(),
        "platform": platform.lower().strip(),
    }
