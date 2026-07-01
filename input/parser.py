"""Command and autocomplete parsing with robust error handling."""

import asyncio
from typing import List
from discord import app_commands

from validation.validator import ALL_COUNTRIES, ALL_NICHES
from airtable_client import AirtableClient


# Comprehensive city list for autocomplete
ALL_CITIES = [
    # USA
    "New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia",
    "San Antonio", "San Diego", "Dallas", "San Jose", "Austin", "Jacksonville",
    "Fort Worth", "Columbus", "Charlotte", "Indianapolis", "San Francisco",
    "Seattle", "Denver", "Nashville", "Oklahoma City", "Las Vegas", "Miami",
    "Atlanta", "Minneapolis", "Portland", "Boston", "Detroit",
    # UK
    "London", "Manchester", "Birmingham", "Leeds", "Glasgow", "Liverpool",
    "Edinburgh", "Bristol", "Sheffield", "Cardiff", "Leicester", "Nottingham",
    "Coventry", "Bradford", "Belfast",
    # Canada
    "Toronto", "Montreal", "Vancouver", "Calgary", "Edmonton", "Ottawa",
    "Winnipeg", "Quebec City", "Hamilton", "Mississauga",
    # Australia
    "Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide", "Canberra",
    "Gold Coast", "Newcastle", "Hobart",
    # Germany
    "Berlin", "Hamburg", "Munich", "Cologne", "Frankfurt", "Stuttgart",
    "Dusseldorf", "Leipzig", "Dortmund", "Dresden",
    # France
    "Paris", "Lyon", "Marseille", "Toulouse", "Nice", "Nantes", "Bordeaux",
    "Strasbourg", "Lille",
    # Netherlands
    "Amsterdam", "Rotterdam", "The Hague", "Utrecht", "Eindhoven",
    # Sweden
    "Stockholm", "Gothenburg", "Malmo",
    # Norway
    "Oslo", "Bergen", "Stavanger",
    # Denmark
    "Copenhagen", "Aarhus", "Odense",
    # Switzerland
    "Zurich", "Geneva", "Basel", "Bern",
    # Austria
    "Vienna", "Salzburg", "Graz",
    # Belgium
    "Brussels", "Antwerp", "Ghent",
    # Spain
    "Madrid", "Barcelona", "Seville", "Valencia", "Bilbao",
    # Italy
    "Rome", "Milan", "Naples", "Turin", "Florence", "Venice",
    # Poland
    "Warsaw", "Krakow", "Wroclaw", "Poznan", "Gdansk",
    # Ireland
    "Dublin", "Cork", "Galway",
    # New Zealand
    "Auckland", "Wellington", "Christchurch",
    # Portugal
    "Lisbon", "Porto",
    # UAE
    "Dubai", "Abu Dhabi",
    # Singapore
    "Singapore",
    # South Africa
    "Cape Town", "Johannesburg", "Durban",
]


async def country_autocomplete(interaction, current: str):
    try:
        current_lower = current.lower()
        matches = [c for c in ALL_COUNTRIES if current_lower in c.lower()][:25]
        return [app_commands.Choice(name=c, value=c) for c in matches]
    except Exception:
        return []


async def niche_autocomplete(interaction, current: str):
    try:
        current_lower = current.lower()
        matches = [n for n in ALL_NICHES if current_lower in n.lower()][:25]
        return [app_commands.Choice(name=n, value=n) for n in matches]
    except Exception:
        return []


async def city_autocomplete(interaction, current: str):
    try:
        current_lower = current.lower()
        matches = [c for c in ALL_CITIES if current_lower in c.lower()][:25]
        return [app_commands.Choice(name=c, value=c) for c in matches]
    except Exception:
        return []


async def order_id_autocomplete(interaction, current: str):
    try:
        db = AirtableClient()
        records = await asyncio.to_thread(db.fetch_all, "Deals")
        ids = [r["fields"].get("OrderID", "") for r in records if r["fields"].get("OrderID")]
        current_upper = current.upper()
        matches = [i for i in ids if current_upper in i][:25]
        return [app_commands.Choice(name=i, value=i) for i in matches]
    except Exception:
        return []
