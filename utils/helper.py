"""General helper utilities used across the system."""

import random
import string
from datetime import datetime
from typing import Optional

import discord

from config import Config

COUNTRY_CODES = {
    "United States": "US", "United Kingdom": "UK", "Canada": "CA",
    "Australia": "AU", "Germany": "DE", "France": "FR",
    "Netherlands": "NL", "Sweden": "SE", "Norway": "NO",
    "Denmark": "DK", "Switzerland": "CH", "Spain": "ES",
    "Italy": "IT", "Ireland": "IE", "Belgium": "BE",
    "Finland": "FI", "Austria": "AT", "Poland": "PL",
    "Portugal": "PT", "New Zealand": "NZ",
    # FIX: Pakistan + Middle East + Asia add kiye
    "Pakistan":       "PK", "Saudi Arabia":  "SA", "Qatar":      "QA",
    "Kuwait":         "KW", "Bahrain":        "BH", "Oman":       "OM",
    "Jordan":         "JO", "Egypt":          "EG", "Turkey":     "TR",
    "India":          "IN", "Bangladesh":     "BD", "Malaysia":   "MY",
    "Indonesia":      "ID", "Philippines":    "PH", "Nigeria":    "NG",
    "Kenya":          "KE", "Ghana":          "GH", "Singapore":  "SG",
    "United Arab Emirates": "AE",
    "Mexico": "MX", "Brazil": "BR", "Argentina": "AR",
    "Colombia": "CO", "Chile": "CL",
}

SERP_COUNTRY_CODES = {
    "United States": "us", "United Kingdom": "uk", "Canada": "ca",
    "Australia": "au", "Germany": "de", "France": "fr",
    "Netherlands": "nl", "Sweden": "se", "Norway": "no",
    "Denmark": "dk", "Finland": "fi", "Switzerland": "ch",
    "Austria": "at", "Belgium": "be", "Spain": "es",
    "Italy": "it", "Poland": "pl", "Ireland": "ie",
    "New Zealand": "nz", "Portugal": "pt",
}


def generate_order_id(niche: str, country: str) -> str:
    """Format: SMMA-[NICHE]-[COUNTRY]-[YYMM]-[RANDOM4]"""
    niche_code = niche.upper()[:3].replace(" ", "")
    country_code = COUNTRY_CODES.get(country, "INT")
    year_month = datetime.now().strftime("%y%m")
    rand_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"SMMA-{niche_code}-{country_code}-{year_month}-{rand_part}"


async def get_or_create_channel(guild: discord.Guild, name: str) -> discord.TextChannel:
    ch = discord.utils.get(guild.text_channels, name=name)
    if not ch:
        ch = await guild.create_text_channel(name)
    return ch


def lead_score_color(score: int) -> int:
    if score >= 7:
        return 0xE74C3C
    if score >= 4:
        return 0xF39C12
    return 0x2ECC71
