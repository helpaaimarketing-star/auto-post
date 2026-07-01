"""
PostGenerator — Existing Instagram posts ko reference lekar nayi posts generate karta hai.

Flow:
1. Profile URL se username nikalo
2. Apify se recent posts fetch karo (captions, likes, types)
3. AI ko real posts ka context do taake woh same style/tone mein naya content banaye
4. Fallback: agar scraping fail ho toh niche-based enriched weak points se kaam chalo
"""

import logging
import re
from typing import Dict, Any, List, Optional

from processing.instagram_scraper import InstagramScraper, summarize_posts_for_ai
from processing.trend_fetcher import fetch_trending_topics

logger = logging.getLogger("PostGenerator")

# Problems jo batate hain ke humara scraper social profile properly read nahi kar saka
_SOCIAL_BLOCK_KEYWORDS = [
    "bot cannot read",
    "privacy blocks",
    "social media profile",
    "cannot read direct",
]


def _is_social_only_profile(analysis_data: Dict[str, Any]) -> bool:
    problems = analysis_data.get("problems", [])
    for p in problems:
        if any(k in p.lower() for k in _SOCIAL_BLOCK_KEYWORDS):
            return True
    title = analysis_data.get("title", "")
    return title.startswith("Social Profile:") or (
        "@" in title and not analysis_data.get("description", "").strip()
    )


def _extract_username(analysis_data: Dict[str, Any]) -> str:
    """@username nikalo — title, description, ya URL se."""
    title = analysis_data.get("title", "")
    for part in title.split():
        if part.startswith("@"):
            return part.lstrip("@")

    url = analysis_data.get("url", "")
    if url:
        parts = [p for p in url.rstrip("/").split("/") if p]
        if parts:
            return parts[-1].lstrip("@")
    return ""


def _build_enriched_weak_points(
    analysis_data: Dict[str, Any],
    niche: str,
    is_social_only: bool,
) -> List[str]:
    raw = analysis_data.get("problems", [])
    if not is_social_only:
        return raw

    # Bot-block wali useless problem hata do
    filtered = [
        p for p in raw
        if not any(k in p.lower() for k in _SOCIAL_BLOCK_KEYWORDS)
    ]

    niche_lower = niche.lower()
    generic_hooks = [
        "No clear product/service showcase in recent posts",
        "Missing strong call-to-action in captions",
        "Inconsistent posting schedule hurting reach",
        "Low engagement despite follower count — content not resonating",
        "No use of Reels/video content — missing high-reach format",
    ]
    niche_specific = {
        "clothing":    ["No outfit styling tips or lookbook content", "Missing 'new arrival' drop announcements", "No behind-the-scenes of product sourcing"],
        "fitness":     ["No transformation posts or client results", "Missing workout tips/how-to Reels", "No meal prep or nutrition content"],
        "food":        ["No dish close-up photography to drive cravings", "Missing recipe videos or process Reels", "No limited-time offer or daily special posts"],
        "real estate": ["No virtual tours or property walkthrough videos", "Missing client testimonial posts", "No market update content"],
        "beauty":      ["No before/after transformation content", "Missing tutorial Reels", "No user-generated content or client reviews"],
        "tech":        ["No product demo or use-case Reels", "Missing explainer content", "No comparison posts"],
        "education":   ["No student success story posts", "Missing educational Reels", "No enrollment deadline posts"],
    }
    extras = generic_hooks[:3]
    for key, tips in niche_specific.items():
        if key in niche_lower:
            extras = tips + generic_hooks[:2]
            break
    return filtered + extras


class PostGenerator:
    """
    Generates 5 improved post templates.
    Agar profile Instagram URL hai toh pehle real posts scrape karta hai
    aur AI ko reference deta hai — same style/tone mein nayi posts banata hai.
    """

    def __init__(self, ai_agent):
        self.ai = ai_agent
        self.ig_scraper = InstagramScraper()

    def generate_templates(
        self,
        analysis_data: Dict[str, Any],
        business_name: str,
        niche: str,
    ) -> Dict[str, Any]:
        """
        Main entry point.
        1. Existing posts scrape karo (Instagram)
        2. AI ko real post context + weak points do
        3. 5 improved posts generate karo
        """
        is_social = _is_social_only_profile(analysis_data)
        username = _extract_username(analysis_data) if is_social else ""

        # Business name fix
        effective_name = business_name
        if is_social and (not business_name or business_name.startswith("Social Profile:")):
            effective_name = f"@{username}" if username else business_name

        # ── Step 1: Real posts fetch karo ─────────────────────────────
        existing_posts: List[Dict] = []
        posts_summary: str = ""

        # Priority 1: Manual captions pasted by user in /analyze command
        manual_posts = analysis_data.get("manual_sample_posts", [])
        if manual_posts:
            existing_posts = manual_posts
            posts_summary = summarize_posts_for_ai(existing_posts)
            logger.info(f"✅ Using {len(existing_posts)} manually provided captions")

        # Priority 2: Apify / HTML scrape
        if not existing_posts and username:
            try:
                existing_posts = self.ig_scraper.fetch_recent_posts(username, limit=9)
                posts_summary = summarize_posts_for_ai(existing_posts)
                if existing_posts:
                    logger.info(f"✅ {len(existing_posts)} real posts fetched for @{username}")
                else:
                    logger.info(f"⚠️ No posts fetched for @{username} — using enriched fallback")
            except Exception as e:
                logger.warning(f"Instagram scraping failed for @{username}: {e}")

        # ── Step 1b: Trending topics fetch (SerpAPI) ────────────────
        trending_info = ""
        try:
            trending_info = fetch_trending_topics(niche)
        except Exception as _te:
            logger.warning(f"Trend fetch failed: {_te}")

        # ── Step 2: Weak points build karo ────────────────────────────
        weak_points = _build_enriched_weak_points(analysis_data, niche, is_social)

        # ── Step 3: Context build karo ────────────────────────────────
        context = {
            "title": analysis_data.get("title", ""),
            "description": analysis_data.get("description", ""),
            "existing_posts_summary": posts_summary,
            "has_real_posts": bool(existing_posts),
            "trending_info": trending_info,
            "posts_count": len(existing_posts),
        }

        # Description enrich karo
        if is_social and username:
            if existing_posts:
                context["description"] = (
                    f"Instagram brand account @{username} in the {niche} niche. "
                    f"We have scraped their last {len(existing_posts)} posts (see above). "
                    f"Analyze their content style, caption tone, hashtag strategy, and "
                    f"engagement patterns — then create 5 NEW posts that match their brand "
                    f"voice but fix their weak points and dramatically improve performance."
                )
            else:
                context["description"] = (
                    f"Instagram brand account @{username} in the {niche} niche. "
                    f"Generate highly specific, realistic, and commercial posts as their "
                    f"professional social media manager. Invent real product names, offers, "
                    f"and content ideas specific to this niche."
                )

        # ── Step 4: AI analysis + post generation ─────────────────────
        analysis_reasoning = self.ai.analyze_post_quality(
            effective_name, niche, weak_points,
            existing_posts_summary=posts_summary,
        )

        templates = self.ai.generate_improved_posts(
            effective_name, niche, weak_points, "instagram",
            count=5, context=context,
        )

        return {
            "post_analysis": analysis_reasoning,
            "templates": templates,
            "scraped_posts_count": len(existing_posts),
        }


__all__ = ["PostGenerator"]
