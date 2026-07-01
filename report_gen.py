"""Weak-point report generation with AI executive summary."""

import logging
from collections import Counter
from datetime import datetime
from typing import Dict, List

from airtable_client import AirtableClient
from ai_agent import AIAgent

logger = logging.getLogger("ReportGenerator")


class ReportGenerator:
    """Builds Airtable-backed reports from lead and outcome data, including AI insights."""

    def __init__(self):
        self.db = AirtableClient()
        self.ai = AIAgent()

    def build_weak_point_report(self, niche: str = "", city: str = "",
                                country: str = "") -> Dict:
        formulas: List[str] = []
        if niche:
            formulas.append(f"{{Niche}}='{niche}'")
        if city:
            formulas.append(f"{{City}}='{city}'")
        if country:
            formulas.append(f"{{Country}}='{country}'")
        formula = "AND(" + ",".join(formulas) + ")" if len(formulas) > 1 else (formulas[0] if formulas else None)

        records = self.db.fetch_all("Raw Dump", formula=formula)
        weak_points: List[str] = []
        total_score = 0
        for record in records:
            fields = record.get("fields", {})
            total_score += int(fields.get("WeaknessScore") or 0)
            raw_points = fields.get("WeakPoints", "")
            weak_points.extend([p.strip("- ").strip() for p in raw_points.splitlines() if p.strip()])

        count = len(records)
        top_points = Counter(weak_points).most_common(8)
        avg_score = round(total_score / count, 2) if count else 0.0

        title = f"Weak-point report: {niche or 'All niches'}"

        # Generate AI Summary
        ai_summary = "No data to summarize."
        if count > 0:
            try:
                ai_summary = self.ai.generate_report_summary(
                    title, niche or "All", city or "All", country or "All",
                    count, avg_score, top_points
                )
            except Exception as e:
                logger.warning(f"AI Report summary failed: {e}")
                ai_summary = "Failed to generate AI summary."

        report = {
            "title": title,
            "niche": niche or "All",
            "city": city or "All",
            "country": country or "All",
            "lead_count": count,
            "avg_weakness_score": avg_score,
            "top_weak_points": top_points,
            "ai_summary": ai_summary,
            "created_at": datetime.now().isoformat(),
        }
        return report

    def save_report(self, report: Dict) -> bool:
        top_points_text = "\n".join(f"{name}: {count}" for name, count in report["top_weak_points"])
        fields = {
            "Title": report["title"],
            "Niche": report["niche"],
            "City": report["city"],
            "Country": report["country"],
            "LeadCount": report["lead_count"],
            "AvgWeaknessScore": report["avg_weakness_score"],
            "TopWeakPoints": f"{top_points_text}\n\n🤖 AI SUMMARY:\n{report['ai_summary']}",
            "CreatedAt": report["created_at"],
        }
        try:
            self.db.create("Reports", fields)
            return True
        except Exception as exc:
            logger.warning(f"Report save failed: {exc}")
            return False


__all__ = ["ReportGenerator"]
