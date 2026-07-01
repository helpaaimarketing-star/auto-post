"""Authentication and authorization validation."""

import logging
from config import Config

logger = logging.getLogger("AuthValidator")


class AuthValidator:
    """Validates system credentials and optional orchestrator secret."""

    @staticmethod
    def validate_config() -> bool:
        required = {
            "AIRTABLE_API_KEY": Config.AIRTABLE_API_KEY,
            "AIRTABLE_BASE_ID": Config.AIRTABLE_BASE_ID,
            "DISCORD_BOT_TOKEN": Config.DISCORD_BOT_TOKEN,
            "GROQ_API_KEY": Config.GROQ_API_KEY,
            "OPENROUTER_API_KEY": Config.OPENROUTER_API_KEY,
            "GMAIL_USER": Config.SMTP_USER,
            "GMAIL_APP_PASSWORD": Config.SMTP_PASSWORD,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            logger.critical(f"Missing environment variables: {missing}")
            return False
            
        if not Config.APIFY_API_TOKEN and not Config.PHANTOMBUSTER_API_KEY:
            logger.critical("Missing at least one scraper key: APIFY_API_TOKEN or PHANTOMBUSTER_API_KEY")
            return False
            
        logger.info("All configs loaded successfully.")
        return True

    @staticmethod
    def verify_orchestrator_secret(provided: str) -> bool:
        if not Config.ORCHESTRATOR_SECRET:
            return True
        return provided == Config.ORCHESTRATOR_SECRET
