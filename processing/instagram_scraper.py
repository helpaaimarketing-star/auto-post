"""
Instagram Post Scraper
Priority:
  1. Apify `apify~instagram-scraper` (posts wala actor — needs APIFY_API_TOKEN)
  2. Direct HTML scrape via shared data JSON (works without any key, public profiles only)
"""

import json
import logging
import re
import time
from typing import Dict, Any, List

import requests

from config import Config

logger = logging.getLogger("InstagramScraper")

_APIFY_BASE     = "https://api.apify.com/v2"
_APIFY_IG_ACTOR = "apify~instagram-scraper"   # posts wala — sahi actor
_DEFAULT_LIMIT  = 9
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# ─── Apify path ───────────────────────────────────────────────────────────────

def _apify_poll(run_id: str, api_key: str, max_wait: int = 120) -> Dict:
    url = f"{_APIFY_BASE}/actor-runs/{run_id}"
    for _ in range(max_wait // 5):
        time.sleep(5)
        r = requests.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=15)
        st = r.json().get("data", {})
        if st.get("status") in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            return st
    return {}


def _apify_fetch_dataset(dataset_id: str, api_key: str, limit: int = 20) -> List[Dict]:
    url = f"{_APIFY_BASE}/datasets/{dataset_id}/items?limit={limit}"
    r = requests.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=20)
    return r.json() if r.status_code == 200 else []


def _fetch_via_apify(username: str, limit: int) -> List[Dict]:
    api_key = Config.APIFY_API_TOKEN
    if not api_key:
        return []
    try:
        payload = {
            "directUrls": [f"https://www.instagram.com/{username}/"],
            "resultsType": "posts",
            "resultsLimit": limit,
            "addParentData": False,
        }
        resp = requests.post(
            f"{_APIFY_BASE}/acts/{_APIFY_IG_ACTOR}/runs",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=20,
        )
        if resp.status_code not in (200, 201):
            logger.error(f"Apify start failed: {resp.status_code} {resp.text[:200]}")
            return []
        run_id = resp.json().get("data", {}).get("id")
        if not run_id:
            return []
        st = _apify_poll(run_id, api_key)
        if st.get("status") != "SUCCEEDED":
            logger.warning(f"Apify run {st.get('status')} for @{username}")
            return []
        dataset_id = st.get("defaultDatasetId")
        raw = _apify_fetch_dataset(dataset_id, api_key, limit=limit + 5)
        logger.info(f"Apify returned {len(raw)} items for @{username}")
        return raw
    except Exception as e:
        logger.error(f"Apify fetch error: {e}")
        return []


# ─── Direct HTML scrape path (no key needed) ─────────────────────────────────

def _fetch_via_html(username: str, limit: int) -> List[Dict]:
    """
    Instagram public profile se shared_data JSON parse karo.
    Works for public profiles. Returns raw post dicts.
    """
    try:
        url = f"https://www.instagram.com/{username}/"
        r = requests.get(url, headers=_HEADERS, timeout=20)
        if r.status_code != 200:
            logger.warning(f"HTML scrape got {r.status_code} for @{username}")
            return []

        html = r.text

        # Method 1: window._sharedData JSON
        m = re.search(r"window\._sharedData\s*=\s*(\{.+?\});</script>", html, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
                user = (
                    data.get("entry_data", {})
                        .get("ProfilePage", [{}])[0]
                        .get("graphql", {})
                        .get("user", {})
                )
                edges = (
                    user.get("edge_owner_to_timeline_media", {})
                        .get("edges", [])
                )
                if edges:
                    logger.info(f"HTML shared_data: got {len(edges)} posts for @{username}")
                    return [e.get("node", {}) for e in edges[:limit]]
            except Exception:
                pass

        # Method 2: __additionalDataLoaded / ProfilePageContainer JSON
        patterns = [
            r'"edge_owner_to_timeline_media"\s*:\s*(\{"count".*?"edges"\s*:\s*\[.*?\]\s*\})',
            r'"edge_hashtag_to_media"\s*:\s*(\{"count".*?"edges"\s*:\s*\[.*?\]\s*\})',
        ]
        for pat in patterns:
            m2 = re.search(pat, html, re.DOTALL)
            if m2:
                try:
                    media = json.loads(m2.group(1))
                    edges = media.get("edges", [])
                    if edges:
                        logger.info(f"HTML regex: got {len(edges)} posts for @{username}")
                        return [e.get("node", {}) for e in edges[:limit]]
                except Exception:
                    pass

        # Method 3: Extract captions from meta tags as last resort
        captions = re.findall(r'"text"\s*:\s*"([^"]{20,500})"', html)
        if captions:
            logger.info(f"HTML meta fallback: {len(captions)} captions for @{username}")
            return [{"edge_media_to_caption": {"edges": [{"node": {"text": c}}]}} for c in captions[:limit]]

        logger.warning(f"HTML scrape: no posts found for @{username} (private or blocked)")
        return []

    except Exception as e:
        logger.error(f"HTML scrape error for @{username}: {e}")
        return []


# ─── Parser ───────────────────────────────────────────────────────────────────

def _parse_posts(raw_items: List[Dict], limit: int) -> List[Dict]:
    posts = []
    for item in raw_items:
        # Caption — handle both Apify and raw IG graph formats
        caption = (
            item.get("caption")
            or item.get("alt")
            or item.get("accessibility_caption")
            or (
                item.get("edge_media_to_caption", {})
                    .get("edges", [{}])[0]
                    .get("node", {})
                    .get("text", "")
            )
            or ""
        ).strip()[:500]

        hashtags = re.findall(r"#\w+", caption)

        likes    = (item.get("likesCount")
                    or item.get("likes_count")
                    or item.get("edge_liked_by", {}).get("count")
                    or item.get("edge_media_preview_like", {}).get("count")
                    or 0)
        comments = (item.get("commentsCount")
                    or item.get("comments_count")
                    or item.get("edge_media_to_comment", {}).get("count")
                    or 0)

        shortcode = item.get("shortCode") or item.get("shortcode") or ""
        post_url  = item.get("url") or (f"https://instagram.com/p/{shortcode}" if shortcode else "")
        media_type = (item.get("type") or item.get("mediaType") or item.get("__typename") or "image").lower()
        if "video" in media_type or "reel" in media_type:
            media_type = "video"
        elif "sidecar" in media_type or "carousel" in media_type:
            media_type = "sidecar"
        else:
            media_type = "image"

        if caption or int(likes) > 0:
            posts.append({
                "caption":   caption,
                "likes":     int(likes),
                "comments":  int(comments),
                "type":      media_type,
                "hashtags":  hashtags[:15],
                "url":       post_url,
            })

        if len(posts) >= limit:
            break

    posts.sort(key=lambda p: p["likes"] + p["comments"] * 2, reverse=True)
    return posts


# ─── Public API ───────────────────────────────────────────────────────────────

class InstagramScraper:
    def fetch_recent_posts(self, username: str, limit: int = _DEFAULT_LIMIT) -> List[Dict]:
        clean = username.lstrip("@").strip()
        if not clean:
            return []

        # Try Apify first (most reliable)
        raw = _fetch_via_apify(clean, limit)

        # Fallback: direct HTML scrape
        if not raw:
            logger.info(f"Apify unavailable — trying HTML scrape for @{clean}")
            raw = _fetch_via_html(clean, limit)

        posts = _parse_posts(raw, limit)
        logger.info(f"Total parsed posts for @{clean}: {len(posts)}")
        return posts


def summarize_posts_for_ai(posts: List[Dict]) -> str:
    if not posts:
        return ""

    lines = ["=== EXISTING POSTS (Reference ke liye — in posts ka style, tone, aur hashtags copy karo) ==="]
    for i, p in enumerate(posts[:6], 1):
        label = {"video": "🎥 Reel/Video", "sidecar": "📸 Carousel", "image": "🖼️ Image"}.get(p["type"], "📷 Post")
        lines.append(
            f"\nPost {i} [{label}] — ❤️ {p['likes']:,} likes | 💬 {p['comments']:,} comments\n"
            f"Caption: {p['caption'][:350] or '(no caption)'}\n"
            f"Hashtags used: {' '.join(p['hashtags'][:10]) or 'none'}"
        )

    if len(posts) >= 2:
        avg_likes = sum(p["likes"] for p in posts) // len(posts)
        best = posts[0]
        lines.append(
            f"\n=== ENGAGEMENT INSIGHTS ===\n"
            f"Average likes: {avg_likes:,}\n"
            f"Best type: {best['type']} | Best caption preview: {best['caption'][:120]}"
        )

    return "\n".join(lines)


__all__ = ["InstagramScraper", "summarize_posts_for_ai"]
