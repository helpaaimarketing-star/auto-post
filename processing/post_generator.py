import logging
from typing import Dict, Any, List
import asyncio
import requests
from config import Config
logger = logging.getLogger("PostGenerator")
class PostGenerator:
    """Generates 5 improved post templates based on analysis findings."""
    
    def __init__(self, ai_agent):
        self.ai = ai_agent
        
    def _fetch_trending_topics(self, niche: str) -> str:
        """Fetch latest trends in the niche using SerpAPI."""
        key = Config.SERPAPI_KEY
        if not key:
            logger.info("SerpAPI key not configured. Skipping trending search.")
            return ""
            
        query = f"latest {niche} trends social media ideas"
        try:
            res = requests.get(
                "https://serpapi.com/search.json",
                params={"engine": "google", "q": query, "api_key": key, "num": 5},
                timeout=10,
            )
            if res.status_code == 200:
                results = res.json().get("organic_results", [])
                trends = []
                for r in results[:4]:
                    title = r.get("title", "")
                    snippet = r.get("snippet", "")
                    trends.append(f"- **{title}**: {snippet}")
                logger.info(f"Fetched {len(trends)} trending topics for niche: {niche}")
                return "\n".join(trends)
        except Exception as e:
            logger.warning(f"SerpAPI trending search failed: {e}")
        return ""
        
    def generate_templates(self, analysis_data: Dict[str, Any], business_name: str, niche: str) -> Dict[str, Any]:
        """Synchronous wrapper to generate templates (useful if called in thread)."""
        weak_points = analysis_data.get("problems", [])
        
        # 1. Fetch trending topics via SerpAPI
        trending_summary = self._fetch_trending_topics(niche)
        
        # 2. Analyze why current posts aren't working
        analysis_reasoning = self.ai.analyze_post_quality(business_name, niche, weak_points)
        
        context = {
            "title": analysis_data.get("title", ""),
            "description": analysis_data.get("description", ""),
            "trending_topics": trending_summary
        }
        
        # 3. Generate 5 improved posts
        templates = self.ai.generate_improved_posts(business_name, niche, weak_points, "instagram", count=5, context=context)
        
        return {
            "post_analysis": analysis_reasoning,
            "templates": templates
        }
__all__ = ["PostGenerator"]
