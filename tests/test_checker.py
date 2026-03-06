"""
Unit tests for src.checker.find_deals().
Implemented in TICKET-003.
"""

import pytest
from src.checker import find_deals

# Sample flight fixture
SAMPLE_FLIGHT = {
    "depart_date": "2026-04-10",
    "return_date": "2026-04-14",
    "price": 120.0,
    "airline": "Southwest",
    "link": "https://example.com",
}


def test_deal_within_threshold_is_returned():
    raise NotImplementedError


def test_price_above_threshold_is_excluded():
    raise NotImplementedError


def test_suspiciously_low_price_is_excluded():
    raise NotImplementedError


def test_duplicate_date_pairs_keep_lowest_price():
    raise NotImplementedError


def test_empty_input_returns_empty_list():
    raise NotImplementedError


def test_price_exactly_at_threshold_is_included():
    raise NotImplementedError


def test_price_one_dollar_above_threshold_is_excluded():
    raise NotImplementedError
