import os
import logging
from dotenv import load_dotenv
load_dotenv()
logger = logging.getLogger("SMMA_Config")
class Config:
    # ── Airtable (free at airtable.com) ──────────────────────────────
    AIRTABLE_API_KEY: str = os.environ.get("AIRTABLE_API_KEY", "").strip()
    AIRTABLE_BASE_ID: str = os.environ.get("AIRTABLE_BASE_ID", "").strip()
    # ── Discord ───────────────────────────────────────────────────────
    DISCORD_BOT_TOKEN: str = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    DISCORD_GUILD_ID: str  = os.environ.get("DISCORD_GUILD_ID", "").strip()
    # Discord Channel Names (auto-created if missing)
    LEADS_CHANNEL_NAME:     str = "leads-pipeline"
    MARKETING_CHANNEL_NAME: str = "direct-marketing"
    DEALS_CHANNEL_NAME:     str = "deal-closed"
    BUILDS_CHANNEL_NAME:    str = "post-builds"
    DOWNLOADS_CHANNEL_NAME: str = "post-downloads"
    ANALYSIS_CHANNEL_NAME:  str = "analysis-reports"
    # ── Groq AI (Free forever at console.groq.com) ───────────────────
    GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "").strip()
    GROQ_MODEL:   str = "llama-3.1-8b-instant"
    # ── OpenRouter AI (openrouter.ai) ───────────────────────────────
    OPENROUTER_API_KEY: str = os.environ.get("OPENROUTER_API_KEY", "").strip()
    # For LinkedIn, B2B, educational, thought-leadership content
    OPENROUTER_MODEL_B2B: str = "openai/gpt-oss-120b:free"
    # For Instagram, Facebook, creative ad copies, viral posts
    OPENROUTER_MODEL_SOCIAL: str = "meta-llama/llama-3.3-70b-instruct:free"
    # ── Gmail SMTP (Free) ─────────────────────────────────────────────
    SMTP_HOST:     str = "smtp.gmail.com"
    SMTP_PORT:     int = 587
    SMTP_USER:     str = os.environ.get("GMAIL_USER", "").strip()
    SMTP_PASSWORD: str = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    # ── SerpAPI (legacy — no longer used) ──────────────────────────
    SERPAPI_KEY: str = os.environ.get("SERPAPI_API_KEY", "").strip()
    # ── Apify (apify.com — $5 free credit/month) ──────────────────────
    APIFY_API_TOKEN: str = os.environ.get("APIFY_API_TOKEN", "").strip()
    # ── Phantombuster (phantombuster.com — 2hrs free/month) ───────────
    PHANTOMBUSTER_API_KEY: str = os.environ.get("PHANTOMBUSTER_API_KEY", "").strip()
    # ── Security ──────────────────────────────────────────────────────
    ORCHESTRATOR_SECRET: str = os.environ.get("ORCHESTRATOR_SECRET", "").strip()
    DEBUG: bool = os.environ.get("DEBUG", "false").lower() == "true"
    # ── Target Countries ──────────────────────────────────────────────
    TARGET_COUNTRIES: list = [
        "United States", "United Kingdom", "Canada", "Australia",
        "Germany", "France", "Netherlands", "Sweden", "Norway",
        "Denmark", "Finland", "Switzerland", "Austria", "Belgium",
        "Spain", "Italy", "Poland", "Ireland", "New Zealand",
        "Portugal", "Czech Republic", "Hungary", "Romania",
    ]
    # ── Pricing Table (market rate USD) ───────────────────────────────
    PRICING_TABLE: dict = {
        "restaurant":  {"starter": 299, "growth": 599,  "pro": 999},
        "dental":      {"starter": 499, "growth": 899,  "pro": 1499},
        "salon":       {"starter": 249, "growth": 499,  "pro": 799},
        "gym":         {"starter": 349, "growth": 699,  "pro": 1099},
        "boutique":    {"starter": 299, "growth": 599,  "pro": 999},
        "clinic":      {"starter": 499, "growth": 899,  "pro": 1499},
        "cafe":        {"starter": 249, "growth": 449,  "pro": 749},
        "real_estate": {"starter": 599, "growth": 999,  "pro": 1799},
        "law":         {"starter": 699, "growth": 1199, "pro": 1999},
        "hotel":       {"starter": 399, "growth": 799,  "pro": 1299},
        "spa":         {"starter": 299, "growth": 599,  "pro": 999},
        "fitness":     {"starter": 349, "growth": 699,  "pro": 1099},
        "bakery":      {"starter": 249, "growth": 449,  "pro": 749},
        "default":     {"starter": 299, "growth": 599,  "pro": 999},
    }
    @classmethod
    def validate(cls) -> bool:
        required = {
            "AIRTABLE_API_KEY":   cls.AIRTABLE_API_KEY,
            "AIRTABLE_BASE_ID":   cls.AIRTABLE_BASE_ID,
            "DISCORD_BOT_TOKEN":  cls.DISCORD_BOT_TOKEN,
            "GROQ_API_KEY":       cls.GROQ_API_KEY,
            "OPENROUTER_API_KEY": cls.OPENROUTER_API_KEY,
            "GMAIL_USER":         cls.SMTP_USER,
            "GMAIL_APP_PASSWORD": cls.SMTP_PASSWORD,
        }
        # Scrapers — at least one must be set
        if not cls.APIFY_API_TOKEN and not cls.PHANTOMBUSTER_API_KEY:
            logger.critical("❌ At least one scraper key required: APIFY_API_TOKEN or PHANTOMBUSTER_API_KEY")
            return False
        missing = [k for k, v in required.items() if not v]
        if missing:
            logger.critical(f"❌ Missing environment variables: {missing}")
            return False
        logger.info("✅ All configs loaded successfully.")
        return True
