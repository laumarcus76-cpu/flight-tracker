"""
Unit tests for src.checker.find_deals().
"""

import pytest
from src.checker import find_deals


def _flight(price: float, depart: str = "2026-04-10", ret: str = "2026-04-14",
            airline: str = "Southwest") -> dict:
    return {
        "depart_date": depart,
        "return_date": ret,
        "price": price,
        "airline": airline,
        "link": "https://example.com",
    }


THRESHOLD = 150.0


def test_deal_within_threshold_is_returned():
    deals = find_deals([_flight(120.0)], threshold=THRESHOLD)
    assert len(deals) == 1
    assert deals[0]["price"] == 120.0


def test_price_above_threshold_is_excluded():
    deals = find_deals([_flight(151.0)], threshold=THRESHOLD)
    assert deals == []


def test_suspiciously_low_price_is_excluded():
    deals = find_deals([_flight(9.0)], threshold=THRESHOLD, min_price=10.0)
    assert deals == []


def test_duplicate_date_pairs_keep_lowest_price():
    flights = [
        _flight(140.0, depart="2026-04-10", ret="2026-04-12"),
        _flight(110.0, depart="2026-04-10", ret="2026-04-12"),  # cheaper — should win
        _flight(130.0, depart="2026-04-10", ret="2026-04-12"),
    ]
    deals = find_deals(flights, threshold=THRESHOLD)
    assert len(deals) == 1
    assert deals[0]["price"] == 110.0


def test_empty_input_returns_empty_list():
    assert find_deals([], threshold=THRESHOLD) == []


def test_price_exactly_at_threshold_is_included():
    deals = find_deals([_flight(150.0)], threshold=THRESHOLD)
    assert len(deals) == 1
    assert deals[0]["price"] == 150.0


def test_price_one_dollar_above_threshold_is_excluded():
    deals = find_deals([_flight(151.0)], threshold=THRESHOLD)
    assert deals == []


def test_results_sorted_by_date_ascending():
    flights = [
        _flight(130.0, depart="2026-04-17", ret="2026-04-19"),
        _flight(100.0, depart="2026-04-10", ret="2026-04-12"),
        _flight(145.0, depart="2026-04-24", ret="2026-04-26"),
    ]
    deals = find_deals(flights, threshold=THRESHOLD)
    dates = [d["depart_date"] for d in deals]
    assert dates == sorted(dates)


def test_min_price_exactly_at_boundary_is_included():
    # "below min_price" means price < min_price; price == min_price is valid data
    deals = find_deals([_flight(10.0)], threshold=THRESHOLD, min_price=10.0)
    assert len(deals) == 1
    assert deals[0]["price"] == 10.0


def test_multiple_routes_deduped_independently():
    flights = [
        _flight(120.0, depart="2026-04-10", ret="2026-04-12"),
        _flight(100.0, depart="2026-04-10", ret="2026-04-12"),  # same dates, lower
        _flight(135.0, depart="2026-04-17", ret="2026-04-19"),  # different dates
    ]
    deals = find_deals(flights, threshold=THRESHOLD)
    assert len(deals) == 2
    assert deals[0]["price"] == 100.0
    assert deals[1]["price"] == 135.0
