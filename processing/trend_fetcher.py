"""
Fetch trending topics for a niche using SerpAPI.
Used to make post generation trend-aware.
"""
import logging
import requests
from config import Config

logger = logging.getLogger("TrendFetcher")


def fetch_trending_topics(niche: str) -> str:
    """
    SerpAPI se niche ke trending topics/news fetch karo.
    Returns a short summary string for injecting into AI prompt.
    Empty string agar SerpAPI key nahi ya fail ho.
    """
    if not Config.SERPAPI_KEY:
        return ""

    try:
        params = {
            "q": f"{niche} trending 2025 tips ideas",
            "api_key": Config.SERPAPI_KEY,
            "num": 5,
            "hl": "en",
            "gl": "us",
        }
        resp = requests.get("https://serpapi.com/search.json", params=params, timeout=15)
        if resp.status_code != 200:
            return ""

        data = resp.json()
        results = data.get("organic_results", [])

        lines = []
        for r in results[:5]:
            title = r.get("title", "").strip()
            snippet = r.get("snippet", "").strip()
            if title:
                lines.append(f"- {title}: {snippet[:120]}" if snippet else f"- {title}")

        if not lines:
            return ""

        summary = "TRENDING NOW in this niche:\n" + "\n".join(lines)
        logger.info(f"Fetched {len(lines)} trending topics for '{niche}'")
        return summary

    except Exception as e:
        logger.warning(f"SerpAPI fetch failed: {e}")
        return ""


__all__ = ["fetch_trending_topics"]
