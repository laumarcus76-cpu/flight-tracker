"""
Tests for src.api — date pair generation and trip pattern logic.
"""

from datetime import date, timedelta

import pytest

from src.api import generate_date_pairs
from src.notifier import _trip_type


# ── generate_date_pairs ────────────────────────────────────────────────────────

def test_weekend_pairs_depart_on_friday():
    pairs = generate_date_pairs(3, [["Friday", "Sunday"]])
    for depart, _ in pairs:
        assert date.fromisoformat(depart).weekday() == 4, f"{depart} is not a Friday"


def test_weekend_pairs_return_on_sunday():
    pairs = generate_date_pairs(3, [["Friday", "Sunday"]])
    for _, ret in pairs:
        assert date.fromisoformat(ret).weekday() == 6, f"{ret} is not a Sunday"


def test_weekend_pairs_are_2_day_delta():
    pairs = generate_date_pairs(3, [["Friday", "Sunday"]])
    for depart, ret in pairs:
        delta = (date.fromisoformat(ret) - date.fromisoformat(depart)).days
        assert delta == 2, f"Expected 2-day delta, got {delta} for {depart}→{ret}"


def test_long_weekend_pairs_depart_on_thursday():
    pairs = generate_date_pairs(3, [["Thursday", "Monday"]])
    for depart, _ in pairs:
        assert date.fromisoformat(depart).weekday() == 3, f"{depart} is not a Thursday"


def test_long_weekend_pairs_return_on_monday():
    pairs = generate_date_pairs(3, [["Thursday", "Monday"]])
    for _, ret in pairs:
        assert date.fromisoformat(ret).weekday() == 0, f"{ret} is not a Monday"


def test_long_weekend_pairs_are_4_day_delta():
    pairs = generate_date_pairs(3, [["Thursday", "Monday"]])
    for depart, ret in pairs:
        delta = (date.fromisoformat(ret) - date.fromisoformat(depart)).days
        assert delta == 4, f"Expected 4-day delta, got {delta} for {depart}→{ret}"


def test_both_patterns_combined():
    pairs = generate_date_pairs(3, [["Friday", "Sunday"], ["Thursday", "Monday"]])
    fri_sun = [(d, r) for d, r in pairs
               if date.fromisoformat(d).weekday() == 4]
    thu_mon = [(d, r) for d, r in pairs
               if date.fromisoformat(d).weekday() == 3]
    assert len(fri_sun) > 0, "Expected Fri-Sun pairs"
    assert len(thu_mon) > 0, "Expected Thu-Mon pairs"


def test_no_past_dates():
    today = date.today()
    pairs = generate_date_pairs(3, [["Friday", "Sunday"], ["Thursday", "Monday"]])
    for depart, _ in pairs:
        assert date.fromisoformat(depart) > today, f"{depart} is not in the future"


def test_pairs_are_sorted():
    pairs = generate_date_pairs(3, [["Friday", "Sunday"], ["Thursday", "Monday"]])
    assert pairs == sorted(pairs)


def test_no_duplicate_pairs():
    pairs = generate_date_pairs(3, [["Friday", "Sunday"], ["Thursday", "Monday"]])
    assert len(pairs) == len(set(pairs))


def test_return_always_after_depart():
    pairs = generate_date_pairs(3, [["Friday", "Sunday"], ["Thursday", "Monday"]])
    for depart, ret in pairs:
        assert date.fromisoformat(ret) > date.fromisoformat(depart)


# ── _trip_type ─────────────────────────────────────────────────────────────────

def test_trip_type_fri_sun_is_weekend():
    assert _trip_type("2026-04-10", "2026-04-12") == "Weekend (Fri–Sun)"


def test_trip_type_thu_mon_is_long_weekend():
    assert _trip_type("2026-04-09", "2026-04-13") == "Long Weekend (Thu–Mon)"


def test_trip_type_other_delta_shows_days():
    assert _trip_type("2026-04-10", "2026-04-15") == "5-day trip"
