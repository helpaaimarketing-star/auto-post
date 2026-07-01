"""Backward-compatible shim — use processing.data_processor."""

from processing.data_processor import DataProcessor


class LeadScraper:
    """Wraps DataProcessor with the legacy .scrape() API."""

    def __init__(self):
        self._processor = DataProcessor()

    def scrape(self, query: str, niche: str, city: str, country: str, limit: int = 15):
        return self._processor.scrape_leads(query, niche, city, country, limit)


__all__ = ["LeadScraper"]
