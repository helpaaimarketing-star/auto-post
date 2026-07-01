from utils.logger import setup_logging
from utils.helper import generate_order_id, get_or_create_channel, SERP_COUNTRY_CODES


def __getattr__(name):
    if name == "AirtableClient":
        from airtable_client import AirtableClient
        return AirtableClient
    raise AttributeError(f"module {__name__} has no attribute {name}")


__all__ = [
    "setup_logging",
    "AirtableClient",
    "generate_order_id",
    "get_or_create_channel",
    "SERP_COUNTRY_CODES",
]
