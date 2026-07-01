"""Scraping facade for businesses and influencer-style discovery."""

from typing import List, Dict

from processing.data_processor import DataProcessor


class Scraper:
    """v2 scan API backed by the existing lead processor."""

    def __init__(self):
        self.processor = DataProcessor()

    def scan_businesses(self, query: str, niche: str, city: str,
                        country: str, limit: int = 15) -> List[Dict]:
        return self.processor.scrape_leads(query, niche, city, country, limit)

    def scan_influencers(self, niche: str, city: str,
                         country: str, limit: int = 10) -> List[Dict]:
        query = f"{niche} influencers in {city}"
        return self.processor.scrape_leads(query, niche, city, country, limit)


__all__ = ["Scraper"]
