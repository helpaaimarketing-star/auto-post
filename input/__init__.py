from input.input import normalize_scrape_input, normalize_deal_input, normalize_build_input
from input.parser import (
    country_autocomplete, niche_autocomplete,
    city_autocomplete, order_id_autocomplete,
)


def __getattr__(name):
    if name == "DiscordListener":
        from bot import DiscordBot
        return DiscordBot
    elif name == "start_health_server":
        from bot import start_health_server
        return start_health_server
    raise AttributeError(f"module {__name__} has no attribute {name}")


__all__ = [
    "normalize_scrape_input", "normalize_deal_input", "normalize_build_input",
    "country_autocomplete", "niche_autocomplete", "city_autocomplete", "order_id_autocomplete",
    "DiscordListener", "start_health_server",
]
