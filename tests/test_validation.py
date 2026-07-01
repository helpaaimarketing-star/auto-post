"""Basic validation layer tests."""

import pytest
from validation.validator import (
    validate_scrape_input, validate_deal_input, validate_build_input,
)
from processing.rule_engine import RuleEngine
from processing.data_processor import extract_contacts


def test_validate_scrape_input_ok():
    ok, err = validate_scrape_input("Restaurants in London", "Restaurant",
                                      "London", "United Kingdom", 10)
    assert ok is True
    assert err == ""


def test_validate_scrape_input_bad_limit():
    ok, err = validate_scrape_input("query", "Restaurant", "London",
                                      "United Kingdom", 50)
    assert ok is False


def test_validate_deal_input_ok():
    ok, err = validate_deal_input("Test Biz", "Dental", "London",
                                   "United Kingdom", "growth", 499)
    assert ok is True


def test_validate_build_input_ok():
    ok, err = validate_build_input("SMMA-DEN-UK-2606-ABCD", "instagram")
    assert ok is True


def test_rule_engine_pricing():
    rules = RuleEngine()
    pricing = rules.suggest_pricing("Dental", [], "United Kingdom")
    assert pricing["currency"] == "GBP"
    assert pricing["symbol"] == "£"


def test_rule_engine_qualification():
    rules = RuleEngine()
    assert rules.is_qualified_lead(5) is True
    assert rules.is_qualified_lead(2) is False


def test_extract_contacts_email_and_phone():
    text = "Get in touch at hello@brand.com or call us at +1 234-567-8901 or chat on wa.me/923001234567"
    emails, phones = extract_contacts(text)
    assert "hello@brand.com" in emails
    assert "+12345678901" in phones or "12345678901" in phones
    assert "923001234567" in phones

    # Test false positives like dates or random numbers are ignored
    text_false = "Created on 2026-06-22 with order ID 123456789 and 50 followers."
    emails_f, phones_f = extract_contacts(text_false)
    assert len(emails_f) == 0
    assert len(phones_f) == 0
