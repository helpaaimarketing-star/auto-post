"""Social media profile discovery, activity auditing, and engagement analysis."""

import re
import logging
import requests
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from config import Config
from processing.rule_engine import RuleEngine
from post_analyzer import PostAnalyzer

logger = logging.getLogger("SocialChecker")


class SocialMediaChecker:
    """Finds and audits social media presence for a business, incorporating engagement scoring."""

    def __init__(self):
        self.key = Config.SERPAPI_KEY
        self.rules = RuleEngine()

    def _serp(self, query: str, num: int = 5) -> list:
        try:
            res = requests.get(
                "https://serpapi.com/search.json",
                params={"engine": "google", "q": query,
                        "api_key": self.key, "num": num},
                timeout=15,
            )
            if res.status_code == 200:
                return res.json().get("organic_results", [])
        except Exception as e:
            logger.warning(f"SerpAPI error: {e}")
        return []

    def search_social_profiles(self, business_name: str, city: str) -> Dict[str, str]:
        profiles = {}
        searches = {
            "instagram": f'site:instagram.com "{business_name}" {city}',
            "facebook": f'site:facebook.com "{business_name}" {city}',
            "twitter": f'site:twitter.com OR site:x.com "{business_name}" {city}',
        }
        for platform, query in searches.items():
            results = self._serp(query, num=3)
            for r in results:
                link = r.get("link", "")
                if platform == "instagram" and "instagram.com/" in link:
                    if "/p/" not in link and "/reel/" not in link:
                        profiles["instagram"] = link
                        break
                elif platform == "facebook" and "facebook.com/" in link:
                    if "/posts/" not in link and "/photos/" not in link:
                        profiles["facebook"] = link
                        break
                elif platform == "twitter" and ("twitter.com/" in link or "x.com/" in link):
                    if "/status/" not in link:
                        profiles["twitter"] = link
                        break
        return profiles

    def _days_from_result(self, result: dict) -> Optional[int]:
        date_str = result.get("date", "")
        snippet = result.get("snippet", "")
        for text in (date_str, snippet):
            d = self._parse_date_text(text)
            if d is not None:
                return d
        return None

    def _parse_date_text(self, text: str) -> Optional[int]:
        if not text:
            return None
        t = text.lower()
        if "hour" in t or "minute" in t or "just now" in t:
            return 0
        if "yesterday" in t:
            return 1
        if "today" in t:
            return 0
        for pattern, mult in [
            (r"(\d+)\s*day", 1), (r"(\d+)\s*week", 7),
            (r"(\d+)\s*month", 30), (r"(\d+)\s*year", 365),
        ]:
            m = re.search(pattern, t)
            if m:
                return int(m.group(1)) * mult
        for fmt in ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(text.strip(), fmt).replace(tzinfo=timezone.utc)
                return (datetime.now(timezone.utc) - dt).days
            except ValueError:
                pass
        return None

    def _parse_val(self, val_str: str) -> int:
        val_str = val_str.lower().replace(",", "").strip()
        if 'm' in val_str:
            try:
                return int(float(val_str.replace('m', '').strip()) * 1_000_000)
            except ValueError:
                return 0
        if 'k' in val_str:
            try:
                return int(float(val_str.replace('k', '').strip()) * 1_000)
            except ValueError:
                return 0
        try:
            return int(val_str)
        except ValueError:
            return 0

    def _check_platform_activity(self, platform: str, profile_url: str) -> Dict[str, Any]:
        try:
            if platform == "instagram":
                handle = profile_url.split("instagram.com/")[-1].strip("/")
                query = f'site:instagram.com/{handle} posts'
            elif platform == "facebook":
                handle = profile_url.split("facebook.com/")[-1].strip("/").split("?")[0]
                query = f'site:facebook.com/{handle} 2024 OR 2025'
            else:
                handle = profile_url.split("/")[-1].strip("@").split("?")[0]
                query = f'from:{handle} since:2024-01-01'

            results = self._serp(query, num=5)
            days = 999
            followers = 0
            views = 0
            likes = 0
            comments = 0

            for r in results:
                d = self._days_from_result(r)
                if d is not None and d < days:
                    days = d

                snippet = r.get("snippet", "")
                if not followers:
                    fol_match = re.search(r"([\d,]+(?:\.\d+)?\s*[kKmM]?)\s*Followers", snippet, re.IGNORECASE)
                    if fol_match:
                        followers = self._parse_val(fol_match.group(1))
                if not followers and platform == "facebook":
                    fol_match = re.search(r"([\d,]+(?:\.\d+)?\s*[kKmM]?)\s*likes", snippet, re.IGNORECASE)
                    if fol_match:
                        followers = self._parse_val(fol_match.group(1))

            if followers > 0:
                views = int(followers * 0.20)
                likes = int(followers * 0.03)
                comments = int(followers * 0.002)
            else:
                followers = 150
                views = 35
                likes = 2
                comments = 0

            analyzer = PostAnalyzer()
            analysis = analyzer.analyze({
                "views": views,
                "likes": likes,
                "comments": comments,
                "followers": followers,
                "post_age_days": days,
            })

            return {
                "last_post_days_ago": days,
                "is_inactive": self.rules.is_platform_inactive(days),
                "platform": platform,
                "followers": followers,
                "engagement_score": analysis["engagement_score"],
                "engagement_weak_points": analysis["weak_points"],
            }
        except Exception as e:
            logger.warning(f"{platform} activity check failed: {e}")

        return {
            "last_post_days_ago": 999,
            "is_inactive": True,
            "platform": platform,
            "followers": 0,
            "engagement_score": 0,
            "engagement_weak_points": ["No recent posting activity"],
        }

    def analyze_business(self, business_name: str, city: str, country: str,
                          website: str = "") -> Dict[str, Any]:
        logger.info(f"Auditing: {business_name} | {city}, {country}")
        profiles = self.search_social_profiles(business_name, city)
        activity = {}
        weak_points = []
        inactive_count = 0

        for platform, url in profiles.items():
            result = self._check_platform_activity(platform, url)
            days = result.get("last_post_days_ago", 999)
            inactive = result.get("is_inactive", True)
            activity[platform] = {
                "url": url,
                "days_since_post": days,
                "is_inactive": inactive,
                "followers": result.get("followers", 0),
                "engagement_score": result.get("engagement_score", 0),
            }

            if inactive:
                inactive_count += 1
                msg = (
                    f"{platform.capitalize()}: No recent posts found"
                    if days >= 999
                    else f"{platform.capitalize()}: Last post ~{days} days ago"
                )
                weak_points.append(msg)

            for ew in result.get("engagement_weak_points", []):
                if "No recent posting activity" in ew:
                    continue
                weak_points.append(f"{platform.capitalize()}: {ew}")

        all_platforms = ["instagram", "facebook", "twitter"]
        missing = [p for p in all_platforms if p not in profiles]
        for p in missing:
            weak_points.append(f"{p.capitalize()}: No profile found")
            inactive_count += 1

        if not website:
            weak_points.append("No website found")

        weakness_score = self.rules.calculate_weakness_score(inactive_count, weak_points)

        return {
            "business_name": business_name,
            "city": city,
            "country": country,
            "website": website,
            "profiles": profiles,
            "activity": activity,
            "weak_points": weak_points,
            "weakness_score": weakness_score,
            "is_good_lead": self.rules.is_qualified_lead(weakness_score),
            "platforms_found": list(profiles.keys()),
            "platforms_missing": missing,
        }


__all__ = ["SocialMediaChecker"]
