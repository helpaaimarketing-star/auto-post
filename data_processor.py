"""Lead scraping and data transformation pipeline."""

import logging
import requests
from typing import List, Dict, Any, Optional
from config import Config
from airtable_client import AirtableClient
from utils.helper import SERP_COUNTRY_CODES
from validation.check_duplication import DuplicationChecker
from social_checker import SocialMediaChecker

logger = logging.getLogger("DataProcessor")


def _safe_url(raw: str) -> str:
    """Ensure URL has a scheme -- Airtable URL field rejects bare domains."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    if raw.startswith(("http://", "https://")):
        return raw
    return "https://" + raw


def _safe_int(val) -> Optional[int]:
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _safe_float(val) -> Optional[float]:
    try:
        return round(float(val), 1)
    except (TypeError, ValueError):
        return None


class DataProcessor:
    """Handles data transformation, enrichment, and lead pipeline."""

    def __init__(self):
        self.db = AirtableClient()
        self.social = SocialMediaChecker()
        self.dedup = DuplicationChecker()

    def scrape_leads(self, query: str, niche: str, city: str,
                     country: str, limit: int = 15) -> List[Dict[str, Any]]:
        logger.info("Scraping: '{}' | {}, {} (limit={})".format(query, city, country, limit))

        # Dynamic query targeting influencers, startups, online businesses
        if niche.lower() == "influencer":
            search_query = f'{query} (site:instagram.com OR site:tiktok.com OR site:youtube.com)'
        elif niche.lower() == "startup":
            search_query = f'{query} "startup" OR "launch" OR "founder"'
        else:
            search_query = f'{query} (site:instagram.com OR site:tiktok.com OR "startup" OR "store" OR "ecommerce")'
        
        params = {
            "engine": "google",
            "q": search_query,
            "api_key": Config.SERPAPI_KEY,
            "hl": "en",
        }
        if country:
            params["gl"] = SERP_COUNTRY_CODES.get(country, "us")

        try:
            res = requests.get("https://serpapi.com/search.json",
                               params=params, timeout=20)
            if res.status_code != 200:
                logger.error("SerpAPI error {}: {}".format(res.status_code, res.text[:300]))
                return []
            raw = res.json().get("organic_results", [])
            logger.info("Google Search returned {} organic results".format(len(raw)))
        except Exception as e:
            logger.error("SerpAPI request failed: {}".format(e))
            return []

        qualified = []
        for place in raw[:min(limit, 25)]:
            # For organic search, we rely on title, snippet, and link
            name = place.get("title", "").strip()
            website_raw = place.get("link", "") or ""
            snippet = place.get("snippet", "") or ""
            phone = ""
            address = ""
            rating = None
            reviews = None

            if not name:
                continue

            if self.dedup.is_duplicate(name, "google"):
                continue

            logger.info("Auditing social for: {}...".format(name))
            audit = self.social.analyze_business(name, city, country, website_raw)

            if not audit["is_good_lead"]:
                logger.info("Skipping {} -- strong social presence".format(name))
                continue

            weak_points_text = "\n".join(audit["weak_points"]) if audit["weak_points"] else "None detected"
            profiles_text = "\n".join(
                "{}: {}".format(k, v) for k, v in audit["profiles"].items()
            ) if audit["profiles"] else "Not found"

            # Match actual Leads table schema exactly
            fields: Dict[str, Any] = {
                "Name":          name,
                "Niche":         niche,
                "Category":      "organic_search",
                "WeakPoints":    (f"Snippet: {snippet}\n\n" if snippet else "") + weak_points_text + "\n\nSocial Profiles:\n" + profiles_text,
                "LeadScore":     int(audit["weakness_score"]),
                "Status":        "Pending Review",
            }
            if country:
                fields["Country"] = country

            # Optional fields -- only add when non-empty to avoid type-validation errors
            website = _safe_url(website_raw)
            if website:
                fields["Website"] = website       # URL field
            if phone:
                fields["Phone"] = phone            # String/Phone field

            logger.info("Sending to Airtable -- fields: {}".format(list(fields.keys())))

            record = self._safe_create(name, fields)
            if record is None:
                continue

            rec_id = record.get("id", "")
            logger.info("Saved: {} (score={})".format(name, audit["weakness_score"]))
            qualified.append({
                "record_id":         rec_id,
                "name":              name,
                "niche":             niche,
                "city":              city,
                "country":           country,
                "website":           website,
                "phone":             phone,
                "weak_points":       audit["weak_points"],
                "profiles":          audit["profiles"],
                "weakness_score":    audit["weakness_score"],
                "platforms_missing": audit["platforms_missing"],
                "rating":            rating,
                "reviews":           reviews,
            })

        logger.info("Scrape complete -- {} qualified leads saved.".format(len(qualified)))
        return qualified

    def _safe_create(self, name: str, fields: Dict) -> Optional[Dict]:
        """
        Try to save full record to Leads table. If Airtable rejects with 422, fall back to
        essential text-only fields that cannot fail type validation.
        """
        try:
            return self.db.create("Leads", fields)
        except RuntimeError as e:
            err = str(e)
            logger.warning("Full create failed for '{}': {}".format(name, err))

            # Fallback: only guaranteed-safe text / integer fields
            fallback: Dict[str, Any] = {
                "Name":          name,
                "Niche":         fields.get("Niche", ""),
                "Category":      fields.get("Category", "organic_search"),
                "WeakPoints":    fields.get("WeakPoints", ""),
                "LeadScore":     fields.get("LeadScore", 0),
                "Status":        "Pending Review",
            }
            if country:
                fallback["Country"] = country
            try:
                logger.info("Retrying fallback save for '{}'".format(name))
                return self.db.create("Leads", fallback)
            except RuntimeError as e2:
                logger.error("Fallback create also failed for '{}': {}".format(name, e2))
                return None
