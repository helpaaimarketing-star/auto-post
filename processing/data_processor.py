"""Lead scraping via Apify + Phantombuster rotation — Instagram, Facebook, LinkedIn, TikTok, Twitter.
v2.6 — Fixed: Combined Meta+LinkedIn scrapers, dedup by business name, request more results from Ad Library.
"""

import re
import logging
import requests
import json
import os
import time
from typing import List, Dict, Any, Optional, Tuple

from config import Config
from airtable_client import AirtableClient
from utils.helper import SERP_COUNTRY_CODES
from validation.check_duplication import DuplicationChecker

logger = logging.getLogger("DataProcessor")

# ── Apify Actor IDs ──────────────────────────────────────────────────────────
_APIFY_BASE         = "https://api.apify.com/v2"
_APIFY_GOOGLE_ACTOR = "apify~google-search-scraper"

# FIX 1: Sahi actor IDs — Apify API endpoints require tilde (~) not slash (/)
_APIFY_FB_ADS_ACTOR = "renzomacar~facebook-ads-library-scraper"
_APIFY_IG_ACTOR     = "apify~instagram-profile-scraper"
_APIFY_LI_ACTOR     = "apify~linkedin-company-scraper"
_APIFY_TT_ACTOR     = "apify~tiktok-profile-scraper"

# ── Phantombuster API ────────────────────────────────────────────────────────
_PB_BASE = "https://api.phantombuster.com/api/v2"

# FIX 2: PB agent slugs — yeh tumhare PB dashboard se lene hain
# Dashboard → Phantoms → agent ka naam copy karo
_PB_AGENT_SLUGS = {
    "google_search":  "Google-Search-Export",        # ✅ FIXED (was: "google-search-export")
    "linkedin":       "LinkedIn-Search-Export",       # LinkedIn specific
    "instagram":      "Instagram-Profile-Scraper",    # Instagram specific
    "facebook":       "Facebook-Page-Scraper",        # Facebook specific
}


def _safe_url(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    return raw if raw.startswith(("http://", "https://")) else "https://" + raw


def _safe_int(val) -> Optional[int]:
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _parse_k(val_str: str) -> int:
    """Parse follower strings like '12.5K', '1.2M' into integers."""
    if not val_str:
        return 0
    s = val_str.lower().replace(",", "").strip()
    try:
        if "m" in s:
            return int(float(s.replace("m", "")) * 1_000_000)
        if "k" in s:
            return int(float(s.replace("k", "")) * 1_000)
        return int(float(s))
    except ValueError:
        return 0


def extract_contacts(text: str) -> Tuple[set, set]:
    """Extract unique emails and phone/WhatsApp numbers from text snippet."""
    emails = set()
    phones = set()

    email_matches = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    for em in email_matches:
        em_clean = em.strip(".-").lower()
        if len(em_clean) > 5 and "." in em_clean.split("@")[-1]:
            emails.add(em_clean)

    plus_pattern = re.compile(r'\+(\d[\d\s\-\(\)]{6,16}\d)')
    for match in plus_pattern.finditer(text):
        clean = re.sub(r'[^\d\+]', '', match.group(0))
        if 8 <= len(clean) <= 15:
            phones.add(clean)

    prefix_pattern = re.compile(
        r'(?:whatsapp|wa\.me/|phone|call|tel|contact|mob)[\:\s]*(\+?\d[\d\s\-\(\)]{6,16}\d)',
        re.IGNORECASE
    )
    for match in prefix_pattern.finditer(text):
        clean = re.sub(r'[^\d\+]', '', match.group(1))
        if 8 <= len(clean) <= 15:
            phones.add(clean)

    wame_pattern = re.compile(r'wa\.me/(\d{8,15})', re.IGNORECASE)
    for match in wame_pattern.finditer(text):
        phones.add(match.group(1))

    return emails, phones


def _build_search_queries(niche: str, location: str) -> List[str]:
    """Build targeted Google search queries."""
    loc_str = f'"{location.strip()}"' if location.strip() else ""
    niche_lower = niche.lower().strip()

    is_educational = any(k in niche_lower for k in ("school", "coaching", "tutor", "education", "academy", "class"))

    queries = []

    if is_educational:
        queries.append(f'site:facebook.com "{niche}" ("email" OR "phone" OR "contact") {loc_str}'.strip())
        queries.append(f'site:instagram.com "{niche}" ("email" OR "phone" OR "dm") {loc_str}'.strip())
        queries.append(f'"{niche}" "admission" OR "enroll" OR "classes" "contact us" {loc_str}'.strip())
        queries.append(f'site:linkedin.com/company "{niche}" {loc_str}'.strip())
    else:
        platforms = '(instagram.com OR tiktok.com OR facebook.com OR linkedin.com OR twitter.com OR x.com)'
        selling = '("shop now" OR "order now" OR "link in bio" OR "dm to order" OR "buy now" OR "sale" OR "store" OR "business")'

        queries.append(f'{platforms} {selling} {loc_str}'.strip())
        if niche_lower and niche_lower not in ("all", "any", "worldwide"):
            queries.append(f'{platforms} "{niche}" {selling} {loc_str}'.strip())
        queries.append(f'{platforms} "selling" OR "online store" OR "small business" {loc_str}'.strip())
        queries.append(f'{platforms} ("email" OR "contact" OR "whatsapp" OR "@gmail.com") {selling} {loc_str}'.strip())

    return queries


# ─────────────────────────────────────────────────────────────────────────────
# Shared polling helper — used by Apify methods to avoid code duplication
# ─────────────────────────────────────────────────────────────────────────────
def _apify_poll(run_id: str, api_key: str, label: str = "Apify", max_wait: int = 120) -> Dict:
    """
    Poll Apify run until completion. Returns the final run data dict.
    FIX 3: Explicit status check after loop — pehle loop ke baad status
    variable galat value rakh sakta tha edge case mein.
    """
    status_url = f"{_APIFY_BASE}/actor-runs/{run_id}"
    st = {}
    attempts = max_wait // 5

    for attempt in range(attempts):
        time.sleep(5)
        resp = requests.get(
            status_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        st = resp.json().get("data", {})
        status = st.get("status", "")
        logger.info(f"{label} status: {status} (attempt {attempt + 1}/{attempts})")
        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            break

    # FIX 3: Explicit final status check (loop se bahar)
    final_status = st.get("status", "UNKNOWN")
    if final_status != "SUCCEEDED":
        raise RuntimeError(f"{label} run ended with status: {final_status}")

    return st


def _apify_fetch_dataset(dataset_id: str, api_key: str, limit: int = 200) -> List[Dict]:
    """Fetch items from an Apify dataset."""
    items_url = f"{_APIFY_BASE}/datasets/{dataset_id}/items?limit={limit}"
    resp = requests.get(
        items_url,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=20,
    )
    return resp.json()


class DataProcessor:
    """Handles scraping via Apify + Phantombuster rotation with automatic fallback."""

    def __init__(self):
        self.db = AirtableClient()
        self.dedup = DuplicationChecker()
        self._offsets_file = "search_offsets.json"

    # ─────────────────────────────────────────────────────────────────────────
    # FIX 4: Offset storage — disk pe save hoti thi jo Railway/Heroku pe reset
    # hoti thi har restart pe. Ab Airtable mein save hoti hai.
    # ─────────────────────────────────────────────────────────────────────────
    def _get_and_increment_offset(self, key: str) -> int:
        """
        Get current offset for a search key and increment it.
        Airtable mein store karta hai taaki server restarts pe bhi persist rahe.
        Fallback: local file (development ke liye).
        """
        # Try Airtable first
        try:
            records = self.db.fetch_all("Offsets", formula=f"{{Key}}='{key}'")
            if records:
                rec = records[0]
                current = int(rec["fields"].get("Value", 0))
                new_val = (current + 10) % 90
                self.db.update("Offsets", rec["id"], {"Value": new_val})
                return current
            else:
                self.db.create("Offsets", {"Key": key, "Value": 10})
                return 0
        except Exception as e:
            logger.warning(f"Airtable offset failed, using local file: {e}")

        # Fallback to local file (dev mode)
        offsets = {}
        if os.path.exists(self._offsets_file):
            try:
                with open(self._offsets_file, "r") as f:
                    offsets = json.load(f)
            except Exception:
                offsets = {}
        current = offsets.get(key, 0)
        offsets[key] = (current + 10) % 90
        try:
            with open(self._offsets_file, "w") as f:
                json.dump(offsets, f)
        except Exception as ex:
            logger.warning(f"Offset save failed: {ex}")
        return current

    # ─────────────────────────────────────────────────────────────────────────
    # SCRAPER A: Apify Google Search
    # ─────────────────────────────────────────────────────────────────────────
    def _apify_search(self, queries: List[str], num_results: int = 10) -> List[Dict]:
        """Google search via Apify — returns {title, link, snippet} dicts."""
        api_key = Config.APIFY_API_TOKEN
        if not api_key:
            raise RuntimeError("APIFY_API_TOKEN not set")

        logger.info(f"Apify Google: Running {len(queries)} queries...")

        run_url = f"{_APIFY_BASE}/acts/{_APIFY_GOOGLE_ACTOR}/runs"
        payload = {
            "queries":         "\n".join(queries),
            "resultsPerPage":  num_results,
            "maxPagesPerQuery": 1,
            "languageCode":    "en",
            "mobileResults":   False,
        }

        try:
            res = requests.post(
                run_url, json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30,
            )
            if res.status_code not in (200, 201):
                raise RuntimeError(f"Apify Google start failed HTTP {res.status_code}: {res.text[:200]}")

            run_id = res.json().get("data", {}).get("id")
            if not run_id:
                raise RuntimeError("Apify Google did not return a run ID")

            st = _apify_poll(run_id, api_key, label="Apify Google")
            items = _apify_fetch_dataset(st["defaultDatasetId"], api_key)

            results = []
            for item in items:
                for organic in item.get("organicResults", []):
                    results.append({
                        "title":   organic.get("title", ""),
                        "link":    organic.get("url", ""),
                        "snippet": organic.get("description", ""),
                        "source":  "google",
                    })

            logger.info(f"Apify Google returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Apify Google failed: {e}")
            raise RuntimeError(f"Apify Google Error: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # SCRAPER B: Meta Ad Library (Facebook + Instagram active advertisers)
    # FIX 1 APPLIED: Sahi actor ID + sahi payload fields
    # ─────────────────────────────────────────────────────────────────────────
    def _meta_ad_library_search(self, niche: str, country: Optional[str], limit: int = 15) -> List[Dict]:
        """
        Scrape Meta Ad Library for businesses actively running Facebook/Instagram ads.
        Yeh woh businesses deta hai jo actually ads pe paise laga rahe hain — best leads.

        FIX 1: Actor ID fix kiya — apify/facebook-ads-library-scraper
        FIX 3: Polling loop ke baad explicit status check
        """
        api_key = Config.APIFY_API_TOKEN
        if not api_key:
            raise RuntimeError("APIFY_API_TOKEN not set")

        # Country ISO-2 mapping
        country_clean = (country or "").strip()
        country_iso = "ALL"
        if country_clean:
            from utils.helper import COUNTRY_CODES
            iso = COUNTRY_CODES.get(country_clean, "ALL")
            country_iso = "GB" if iso == "UK" else iso
        if country_clean.lower() in ("pakistan", "pk"):
            country_iso = "PK"
        if country_clean.lower() == "china":
            country_iso = "CN"

        logger.info(f"Meta Ad Library: niche='{niche}' country='{country_iso}' limit={limit}")

        run_url = f"{_APIFY_BASE}/acts/{_APIFY_FB_ADS_ACTOR}/runs"

        payload = {
            "searchQuery":    niche,
            "country":        country_iso,
            "activeStatus":   "active",
            "adType":         "all",
            "maxResults":     limit,
        }

        try:
            res = requests.post(
                run_url, json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30,
            )
            if res.status_code not in (200, 201):
                raise RuntimeError(f"Meta Ad Library start failed HTTP {res.status_code}: {res.text[:300]}")

            run_id = res.json().get("data", {}).get("id")
            if not run_id:
                raise RuntimeError("Meta Ad Library did not return a run ID")

            logger.info(f"Meta Ad Library run started: {run_id}")

            # FIX 3: _apify_poll use kar raha hai — explicit status check included
            st = _apify_poll(run_id, api_key, label="Meta Ad Library", max_wait=120)
            items = _apify_fetch_dataset(st["defaultDatasetId"], api_key, limit=limit * 3)

            results = []
            for item in items:
                # Ultra robust parsing for different schema versions
                page_name    = item.get("pageName") or item.get("page_name") or item.get("advertiserName") or item.get("pageName") or str(item.get("page", {}).get("pageName", "")) or ""
                page_url     = item.get("pageUrl") or item.get("pageProfileURI") or item.get("page_profile_url") or item.get("advertiserProfileLink") or ""
                ad_body      = item.get("adCreativeBody") or item.get("body_text") or item.get("body") or ""
                ad_title     = item.get("adTitle") or item.get("title") or ""
                page_likes   = item.get("pageLikes") or item.get("page_like_count") or 0
                ig_followers = item.get("instagramFollowers") or 0
                platforms    = item.get("publisherPlatforms") or item.get("publisher_platforms") or []
                phone        = item.get("phoneNumber") or item.get("phone") or ""
                email        = item.get("email") or ""
                website      = item.get("websiteUrl") or item.get("website") or item.get("link_url") or ""

                if not page_name:
                    logger.warning(f"Skipped ad item, no page_name found. Keys: {list(item.keys())}")
                    continue

                # Rich snippet — contact info bhi include karo agar mile
                contact_parts = []
                if phone:
                    contact_parts.append(f"Phone: {phone}")
                if email:
                    contact_parts.append(f"Email: {email}")
                if website:
                    contact_parts.append(f"Web: {website}")

                platform_str = ", ".join(platforms) if platforms else "Facebook/Instagram"
                followers_str = ""
                if ig_followers:
                    followers_str = f" | IG: {ig_followers:,} followers"
                elif page_likes:
                    followers_str = f" | FB: {page_likes:,} likes"

                snippet = (
                    f"Active {platform_str} advertiser{followers_str}. "
                    f"Ad: {(ad_title + ' — ' + ad_body)[:150].strip()}. "
                    f"{' | '.join(contact_parts)}"
                ).strip(". ")

                results.append({
                    "title":   page_name,
                    "link":    page_url or f"https://www.facebook.com/ads/library/?q={page_name}",
                    "snippet": snippet,
                    "source":  "meta_ads",
                    # Extra fields — downstream code mein use honge
                    "_phone":   phone,
                    "_email":   email,
                    "_website": website,
                    "_ig_followers": ig_followers,
                    "_fb_likes":     page_likes,
                })

            logger.info(f"Meta Ad Library returned {len(results)} active advertisers")
            return results

        except Exception as e:
            logger.error(f"Meta Ad Library failed: {e}")
            raise RuntimeError(f"Meta Ad Library Error: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # SCRAPER C: LinkedIn Company Scraper (NEW)
    # FIX: LinkedIn ke liye dedicated scraper — pehle sirf Google dorking tha
    # ─────────────────────────────────────────────────────────────────────────
    def _linkedin_company_search(self, niche: str, location: str, limit: int = 15) -> List[Dict]:
        """
        LinkedIn pe niche-relevant companies dhundho jo ads chala rahi hain.
        Uses apify/linkedin-company-scraper.

        NOTE: LinkedIn ka koi public ads library nahi hai — isliye hum
        companies dhundhte hain, phir unhe directly outreach karte hain.
        """
        api_key = Config.APIFY_API_TOKEN
        if not api_key:
            raise RuntimeError("APIFY_API_TOKEN not set")

        logger.info(f"LinkedIn Scraper: niche='{niche}' location='{location}' limit={limit}")

        run_url = f"{_APIFY_BASE}/acts/{_APIFY_LI_ACTOR}/runs"

        # LinkedIn company scraper ke search queries
        search_query = f"{niche} {location}".strip() if location else niche
        payload = {
            "searchUrl": f"https://www.linkedin.com/search/results/companies/?keywords={requests.utils.quote(search_query)}&origin=GLOBAL_SEARCH_HEADER",
            "maxResults": limit,
        }

        try:
            res = requests.post(
                run_url, json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30,
            )
            if res.status_code not in (200, 201):
                raise RuntimeError(f"LinkedIn scraper start failed HTTP {res.status_code}: {res.text[:200]}")

            run_id = res.json().get("data", {}).get("id")
            if not run_id:
                raise RuntimeError("LinkedIn scraper did not return a run ID")

            logger.info(f"LinkedIn run started: {run_id}")
            st = _apify_poll(run_id, api_key, label="LinkedIn", max_wait=120)
            items = _apify_fetch_dataset(st["defaultDatasetId"], api_key, limit=limit * 2)

            results = []
            for item in items:
                name       = item.get("name", "") or item.get("companyName", "")
                li_url     = item.get("url", "") or item.get("linkedInUrl", "")
                industry   = item.get("industry", "")
                employees  = item.get("employeeCount", "") or item.get("staffCount", "")
                website    = item.get("website", "") or item.get("websiteUrl", "")
                location_r = item.get("location", "") or item.get("headquarter", "")
                desc       = item.get("description", "")[:200] if item.get("description") else ""

                if not name:
                    continue

                size_str = f"{employees} employees" if employees else ""
                snippet = f"LinkedIn company | {industry} | {size_str} | {location_r}. {desc}".strip(" |.")

                results.append({
                    "title":    name,
                    "link":     li_url,
                    "snippet":  snippet,
                    "source":   "linkedin",
                    "_website": website,
                    "_industry": industry,
                })

            logger.info(f"LinkedIn returned {len(results)} companies")
            return results

        except Exception as e:
            logger.error(f"LinkedIn scraper failed: {e}")
            raise RuntimeError(f"LinkedIn Error: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # SCRAPER D: Phantombuster (fallback)
    # FIX 2: Sahi agent slug + proper error handling
    # ─────────────────────────────────────────────────────────────────────────
    def _phantombuster_search(self, queries: List[str], num_results: int = 10) -> List[Dict]:
        """
        Phantombuster Google Search Export — last resort fallback.
        FIX 2: Sahi agent slug use ho raha hai.
        NOTE: Apne PB dashboard se exact slug verify karo.
        """
        api_key = Config.PHANTOMBUSTER_API_KEY
        if not api_key:
            raise RuntimeError("PHANTOMBUSTER_API_KEY not set")

        logger.info("Phantombuster: Starting Google Search Export...")

        launch_url = f"{_PB_BASE}/agents/launch"
        all_results = []

        for query in queries[:5]:
            try:
                payload = {
                    "id":       _PB_AGENT_SLUGS["google_search"],  # FIX 2: sahi slug
                    "argument": json.dumps({
                        "searches":                  [query],
                        "numberOfResultsPerSearch":  num_results,
                        "csvName":                   "result",
                    }),
                }
                res = requests.post(
                    launch_url, json=payload,
                    headers={
                        "X-Phantombuster-Key": api_key,
                        "Content-Type": "application/json",
                    },
                    timeout=30,
                )

                if res.status_code not in (200, 201):
                    logger.warning(f"PB launch failed '{query[:40]}': HTTP {res.status_code} — {res.text[:100]}")
                    continue

                resp_data    = res.json()
                container_id = resp_data.get("containerId") or resp_data.get("id")
                if not container_id:
                    logger.warning(f"PB no container ID for query: {query[:40]}")
                    continue

                # Poll for result
                fetch_url = f"{_PB_BASE}/agents/fetch-output"
                out = {}
                for _ in range(12):
                    time.sleep(5)
                    out = requests.get(
                        fetch_url,
                        params={"id": container_id},
                        headers={"X-Phantombuster-Key": api_key},
                        timeout=15,
                    ).json()
                    if out.get("status") in ("finished", "error"):
                        break

                if out.get("status") == "error":
                    logger.warning(f"PB agent errored for query: {query[:40]}")
                    continue

                output = out.get("output", "")
                for line in output.splitlines():
                    if line.startswith("{"):
                        try:
                            item = json.loads(line)
                            all_results.append({
                                "title":   item.get("title", item.get("name", "")),
                                "link":    item.get("link", item.get("url", "")),
                                "snippet": item.get("snippet", item.get("description", "")),
                                "source":  "phantombuster",
                            })
                        except Exception:
                            pass

            except Exception as e:
                logger.warning(f"PB query failed: {e}")
                continue

        logger.info(f"Phantombuster returned {len(all_results)} results")
        return all_results

    # ─────────────────────────────────────────────────────────────────────────
    # MAIN ROUTING: Platform ke hisaab se sahi scraper choose karta hai
    # ─────────────────────────────────────────────────────────────────────────
    def _fetch_raw_results(
        self,
        queries: List[str],
        niche: str,
        country: Optional[str],
        location: str = "",
        num: int = 10,
        platform_hint: str = "auto",
    ) -> List[Dict]:
        """
        Platform hint ke hisaab se sahi scraper use karta hai.
        platform_hint: "facebook", "instagram", "linkedin", "auto"

        FIX: Meta Ad Library ab try/except ke saath hai — proper error Discord pe jaayega.
        """
        niche_lower      = niche.lower().strip()
        is_educational   = any(k in niche_lower for k in ("school", "coaching", "tutor", "education", "academy", "class"))
        use_meta         = platform_hint in ("facebook", "instagram", "auto") and not is_educational
        use_linkedin     = platform_hint in ("linkedin", "auto")

        errors = []

        all_results = []

        # ── 1. Meta Ad Library (Facebook + Instagram active advertisers) ──
        if use_meta and Config.APIFY_API_TOKEN:
            try:
                results = self._meta_ad_library_search(niche, country, limit=num * 2)
                if results:
                    logger.info(f"Meta Ad Library returned {len(results)} results ✅")
                    all_results.extend(results)
                else:
                    logger.warning("Meta Ad Library returned 0 results")
            except RuntimeError as e:
                err_msg = str(e)
                logger.warning(f"Meta Ad Library failed: {err_msg}")
                errors.append(f"Meta Ads: {err_msg}")

        # ── 2. LinkedIn Company Scraper ───────────────────────────────────
        # Always try LinkedIn in auto mode too (not just when platform_hint == "linkedin")
        if use_linkedin and Config.APIFY_API_TOKEN:
            try:
                results = self._linkedin_company_search(niche, location, limit=num)
                if results:
                    logger.info(f"LinkedIn returned {len(results)} results ✅")
                    all_results.extend(results)
                else:
                    logger.warning("LinkedIn returned 0 results")
            except RuntimeError as e:
                err_msg = str(e)
                logger.warning(f"LinkedIn failed: {err_msg}")
                errors.append(f"LinkedIn: {err_msg}")

        # If we got combined results, return them
        if all_results:
            logger.info(f"Combined scrapers returned {len(all_results)} total results")
            return all_results

        # ── 3. Apify Google Search (fallback) ────────────────────────────
        # Only for Educational niches (Schools/Coaching) or if Ad Library + LinkedIn both failed
        if is_educational or not all_results:
            if Config.APIFY_API_TOKEN:
                try:
                    results = self._apify_search(queries, num_results=num)
                    if results:
                        logger.info(f"Using Apify Google Search results ({len(results)}) ✅")
                        return results
                except RuntimeError as e:
                    err_msg = str(e)
                    logger.warning(f"Apify Google failed: {err_msg}")
                    errors.append(f"Apify Google: {err_msg}")

            # ── 4. Phantombuster (last resort) ────────────────────────────────
            if Config.PHANTOMBUSTER_API_KEY:
                try:
                    results = self._phantombuster_search(queries, num_results=num)
                    if results:
                        logger.info(f"Using Phantombuster results ({len(results)}) ✅")
                        return results
                except RuntimeError as e:
                    err_msg = str(e)
                    logger.warning(f"Phantombuster failed: {err_msg}")
                    errors.append(f"Phantombuster: {err_msg}")

        error_details = " | ".join(errors) if errors else "All scrapers returned 0 results"
        raise RuntimeError(f"Scrapers Failed → {error_details}")

    # ─────────────────────────────────────────────────────────────────────────
    # INTERNAL: Light social audit (snippet-based, no extra API calls)
    # ─────────────────────────────────────────────────────────────────────────
    def _audit_lead_light(self, name: str, website: str, niche: str, source: str = "") -> Dict[str, Any]:
        audit: Dict[str, Any] = {
            "profiles":          {},
            "followers":         {},
            "last_post_days":    {},
            "weak_points":       [],
            "sale_hooks":        [],
            "platforms_missing": [],
            "emails":            set(),
            "phones":            set(),
        }

        url_lower = website.lower()
        if "instagram.com" in url_lower:
            audit["profiles"]["instagram"] = website
        elif "tiktok.com" in url_lower:
            audit["profiles"]["tiktok"] = website
        elif "linkedin.com" in url_lower:
            audit["profiles"]["linkedin"] = website
        elif "twitter.com" in url_lower or "x.com" in url_lower:
            audit["profiles"]["twitter"] = website
        elif "facebook.com" in url_lower:
            audit["profiles"]["facebook"] = website

        # Source-based platform inference
        if source == "meta_ads" and not audit["profiles"]:
            audit["profiles"]["facebook"] = website
        elif source == "linkedin" and not audit["profiles"]:
            audit["profiles"]["linkedin"] = website

        all_platforms = ["instagram", "tiktok", "linkedin", "twitter", "facebook"]
        found   = set(audit["profiles"].keys())
        missing = [p for p in all_platforms if p not in found]
        audit["platforms_missing"] = missing

        for p in missing:
            audit["weak_points"].append(f"No {p.capitalize()} presence found")
            audit["sale_hooks"].append(f"We can set up and grow their {p.capitalize()} account")

        niche_lower = niche.lower()
        if niche_lower == "startup":
            audit["sale_hooks"].append("Daily content posting to grow the brand quickly")
            audit["sale_hooks"].append("Product listing optimization on social media shops")
        elif niche_lower == "influencer":
            audit["sale_hooks"].append("Content calendar + brand partnership outreach strategy")

        score = min(10, len(audit["weak_points"]) * 2 + len(missing))
        audit["weakness_score"] = max(score, 2)
        return audit

    def _audit_lead(self, name: str, website: str, niche: str) -> Dict[str, Any]:
        return self._audit_lead_light(name, website, niche)

    # ─────────────────────────────────────────────────────────────────────────
    # INTERNAL: Safe Airtable create
    # ─────────────────────────────────────────────────────────────────────────
    def _safe_create(self, name: str, fields: Dict) -> Optional[Dict]:
        try:
            return self.db.create("Leads", fields)
        except RuntimeError as e:
            logger.warning(f"Full create failed for '{name}': {e}")
            fallback: Dict[str, Any] = {
                "Name":       name,
                "Niche":      fields.get("Niche", ""),
                "Category":   "organic_search",
                "WeakPoints": fields.get("WeakPoints", ""),
                "LeadScore":  fields.get("LeadScore", 2),
                "Status":     "Pending Review",
            }
            if fields.get("Country"):
                fallback["Country"] = fields["Country"]
            try:
                return self.db.create("Leads", fallback)
            except RuntimeError as e2:
                logger.error(f"Fallback also failed for '{name}': {e2}")
                return None

    # ─────────────────────────────────────────────────────────────────────────
    # PUBLIC: Main scrape entry point
    # ─────────────────────────────────────────────────────────────────────────
    def scrape_leads(
        self,
        query: str,
        niche: str,
        city: Optional[str],
        country: Optional[str],
        limit: int = 15,
        platform_hint: str = "auto",
    ) -> List[Dict[str, Any]]:
        city     = (city or "").strip()
        country  = (country or "").strip()
        location = f"{city} {country}".strip() if (city or country) else ""

        logger.info(f"Scraping: niche='{niche}' | location='{location or 'Worldwide'}' | limit={limit} | platform={platform_hint}")

        queries = _build_search_queries(niche, location)
        logger.info(f"Built {len(queries)} search queries")

        try:
            raw_results = self._fetch_raw_results(
                queries, niche=niche, country=country,
                location=location, num=limit, platform_hint=platform_hint,
            )
        except RuntimeError as e:
            raise RuntimeError(str(e))

        # Deduplicate by URL AND by business name (case-insensitive)
        # Meta Ad Library returns multiple ads per business — we only want each business once
        seen_urls: set = set()
        seen_names: set = set()
        unique_results = []
        for r in raw_results:
            url = r.get("link", "")
            name_lower = r.get("title", "").strip().lower()
            
            # Skip if we already have this URL or this business name
            if url and url in seen_urls:
                continue
            if name_lower and name_lower in seen_names:
                continue
            
            if url:
                seen_urls.add(url)
            if name_lower:
                seen_names.add(name_lower)
            unique_results.append(r)

        logger.info(f"Unique results after dedup: {len(unique_results)}")

        qualified: List[Dict[str, Any]] = []
        for place in unique_results:
            if len(qualified) >= limit:
                break

            name        = place.get("title", "").strip()
            website_raw = place.get("link", "") or ""
            snippet     = place.get("snippet", "") or ""
            source      = place.get("source", "")

            if not name:
                continue
            if self.dedup.is_duplicate(name, source or "google"):
                logger.info(f"Duplicate skipped: {name}")
                continue

            website = _safe_url(website_raw)

            audit = self._audit_lead_light(name, website, niche, source=source)

            # Extract contacts from snippet
            ems, phs = extract_contacts(snippet)
            audit["emails"].update(ems)
            audit["phones"].update(phs)

            # Meta Ads result mein extra contact fields ho sakti hain
            if place.get("_email"):
                audit["emails"].add(place["_email"])
            if place.get("_phone"):
                audit["phones"].add(place["_phone"])
            if place.get("_website") and not website:
                website = _safe_url(place["_website"])
            if place.get("_ig_followers"):
                audit["followers"]["instagram"] = place["_ig_followers"]
            if place.get("_fb_likes"):
                audit["followers"]["facebook"] = place["_fb_likes"]

            emails          = list(audit["emails"])
            phones          = list(audit["phones"])
            profiles        = audit["profiles"]
            weak_points     = audit["weak_points"]
            sale_hooks      = audit["sale_hooks"]
            weakness_score  = audit["weakness_score"]

            if not emails and not phones and not profiles and not website:
                logger.info(f"Skipping '{name}': no contact info")
                continue

            weak_text_parts = []
            if snippet:
                weak_text_parts.append(f"About: {snippet}")
            if weak_points:
                weak_text_parts.append("Issues Found:\n" + "\n".join(f"• {w}" for w in weak_points))
            if sale_hooks:
                weak_text_parts.append("Sale Hooks:\n" + "\n".join(f"• {s}" for s in sale_hooks))
            if profiles:
                weak_text_parts.append("Profiles:\n" + "\n".join(f"{k}: {v}" for k, v in profiles.items()))

            fields: Dict[str, Any] = {
                "Name":       name,
                "Niche":      niche,
                "Category":   source or "organic_search",
                "WeakPoints": "\n\n".join(weak_text_parts),
                "LeadScore":  weakness_score,
                "Status":     "Pending Review",
            }
            if country:
                fields["Country"] = country
            if website:
                fields["Website"] = website
            if emails:
                fields["Email"] = emails[0]
            if phones:
                fields["Phone"] = phones[0]

            record = self._safe_create(name, fields)
            rec_id = record.get("id", "") if record else ""

            qualified.append({
                "record_id":         rec_id,
                "name":              name,
                "niche":             niche,
                "city":              city,
                "country":           country,
                "website":           website,
                "phone":             phones[0] if phones else "",
                "email":             emails[0] if emails else "",
                "weak_points":       weak_points,
                "sale_hooks":        sale_hooks,
                "profiles":          profiles,
                "weakness_score":    weakness_score,
                "platforms_missing": audit.get("platforms_missing", []),
                "followers":         audit.get("followers", {}),
                "last_post_days":    audit.get("last_post_days", {}),
                "snippet":           snippet,
                "source":            source,
                "rating":            None,
                "reviews":           None,
            })
            logger.info(f"Lead saved: {name} (score={weakness_score}, source={source})")

        logger.info(f"Scrape complete — {len(qualified)} leads")
        return qualified
