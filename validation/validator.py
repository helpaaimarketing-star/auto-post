"""Data integrity and format validation. v2.0 — Added School, Coaching Center niches."""

import re
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("Validator")

ALL_COUNTRIES = [
    "United States", "United Kingdom", "Canada", "Australia",
    "Germany", "France", "Netherlands", "Sweden", "Norway",
    "Denmark", "Finland", "Switzerland", "Austria", "Belgium",
    "Spain", "Italy", "Poland", "Ireland", "New Zealand",
    "Portugal", "Czech Republic", "Hungary", "Romania", "Greece",
    "Singapore", "United Arab Emirates", "South Africa",
]

ALL_NICHES = [
    "Influencer", "Startup",
    "Restaurant", "Cafe", "Bakery", "Bar", "Fast Food",
    "Dental", "Clinic", "Pharmacy", "Physiotherapy", "Optician",
    "Salon", "Spa", "Barbershop", "Nail Studio", "Tattoo Studio",
    "Gym", "Fitness Studio", "Yoga Studio", "Pilates Studio",
    "Boutique", "Clothing Store", "Shoe Store", "Jewellery Store",
    "Real Estate", "Property Management", "Mortgage Broker",
    "Law Firm", "Accounting", "Financial Advisor",
    "Hotel", "Bed and Breakfast", "Hostel", "Vacation Rental",
    "Car Dealership", "Auto Repair", "Car Wash",
    "Plumber", "Electrician", "Landscaping", "Cleaning Service",
    "Photography", "Videography", "Interior Design",
    "Tutoring", "Language School", "Driving School",
    "Pet Grooming", "Veterinary", "Pet Store",
    "Florist", "Gift Shop", "Book Store",
    "Marketing Agency", "Graphic Design", "Web Design",
    "Construction", "Architecture", "Engineering",
    "Catering", "Event Planning", "Wedding Venue",
    "Supermarket", "Convenience Store", "Organic Store",
    "School", "Coaching Center",
]

VALID_PACKAGES = {"starter", "growth", "pro"}
VALID_PLATFORMS = {"instagram", "facebook", "twitter"}
EMAIL_RE = re.compile(r"^[\w.+-]+@[\w.-]+\.\w+$")


def validate_scrape_input(query: str, niche: str, city: Optional[str],
                          country: Optional[str], limit: int) -> Tuple[bool, str]:
    if not query.strip():
        return False, "Query cannot be empty."
    if city is not None and not city.strip():
        return False, "City cannot be blank if provided."
    if country is not None and country not in ALL_COUNTRIES:
        return False, f"Invalid country: {country}"
    if limit < 1 or limit > 25:
        return False, "Limit must be between 1 and 25."
    return True, ""


def validate_deal_input(business: str, niche: str, city: str, country: str,
                        package: str, price: int,
                        email: Optional[str] = "") -> Tuple[bool, str]:
    if not business.strip():
        return False, "Business name is required."
    if package not in VALID_PACKAGES:
        return False, f"Invalid package: {package}"
    if price < 50 or price > 50000:
        return False, "Price must be between $50 and $50,000."
    if email and not EMAIL_RE.match(email):
        return False, "Invalid email format."
    return True, ""


def validate_build_input(order_id: str, platform: str) -> Tuple[bool, str]:
    if not order_id.strip():
        return False, "Order ID is required."
    if platform not in VALID_PLATFORMS:
        return False, f"Invalid platform: {platform}"
    return True, ""


def validate_lead_record(fields: Dict) -> Tuple[bool, List[str]]:
    errors = []
    if not fields.get("Name"):
        errors.append("Name missing")
    if not fields.get("Niche"):
        errors.append("Niche missing")
    return len(errors) == 0, errors
