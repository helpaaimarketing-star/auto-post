"""Post and social profile analysis helpers."""

from typing import Dict, List


class PostAnalyzer:
    """Scores simple social metrics into a practical SMMA audit."""

    def engagement_score(self, views: int = 0, likes: int = 0,
                         comments: int = 0, followers: int = 0) -> int:
        reach_base = max(views, followers, 1)
        rate = ((likes + comments * 2) / reach_base) * 100
        return max(0, min(10, round(rate)))

    def analyze(self, metrics: Dict) -> Dict:
        score = self.engagement_score(
            views=int(metrics.get("views") or 0),
            likes=int(metrics.get("likes") or 0),
            comments=int(metrics.get("comments") or 0),
            followers=int(metrics.get("followers") or 0),
        )
        weak_points: List[str] = []
        if score < 3:
            weak_points.append("Low engagement compared with audience size")
        if int(metrics.get("post_age_days") or 0) > 14:
            weak_points.append("No recent posting activity")
        if int(metrics.get("views") or 0) < 250:
            weak_points.append("Low content reach")
        if not weak_points:
            weak_points.append("Content is active; improve conversion CTA")
        return {"engagement_score": score, "weak_points": weak_points}


__all__ = ["PostAnalyzer"]
