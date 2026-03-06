"""
SerpAPI Google Flights client.

Two-call round-trip flow:
  Call 1: fetch outbound flights → get departure_token per itinerary
  Call 2: fetch return flights using departure_token → get combined round-trip price

Usage:
  python -m src.api
"""

import os
import time
from datetime import date, timedelta
from typing import Iterator

from serpapi import GoogleSearch


def get_cheapest_round_trips(
    origin: str,
    destination: str,
    date_pairs: list[tuple[str, str]],
    api_key: str,
) -> list[dict]:
    """
    Fetch the cheapest round-trip fares for each (depart_date, return_date) pair.

    Args:
        origin: IATA code, e.g. "SFO"
        destination: IATA code, e.g. "LAS"
        date_pairs: list of ("YYYY-MM-DD", "YYYY-MM-DD") tuples
        api_key: SerpAPI key

    Returns:
        List of dicts with keys: depart_date, return_date, price, airline, link
        Returns empty list if no results found. Raises on API errors.
    """
    raise NotImplementedError


def generate_date_pairs(
    months: list[str],
    min_days: int = 2,
    max_days: int = 7,
) -> list[tuple[str, str]]:
    """
    Generate (depart_date, return_date) pairs for all Fri→Sun combinations
    within the given months, filtered by trip length bounds.

    Args:
        months: list of "YYYY-MM" strings, e.g. ["2026-04", "2026-05"]
        min_days: minimum trip length in days
        max_days: maximum trip length in days

    Returns:
        List of ("YYYY-MM-DD", "YYYY-MM-DD") tuples
    """
    raise NotImplementedError


if __name__ == "__main__":
    import json

    api_key = os.environ.get("SERPAPI_KEY", "")
    if not api_key:
        raise SystemExit("SERPAPI_KEY environment variable not set")

    pairs = generate_date_pairs(["2026-04"], min_days=2, max_days=4)
    print(f"Generated {len(pairs)} date pairs")

    results = get_cheapest_round_trips("SFO", "LAS", pairs[:2], api_key)
    print(json.dumps(results, indent=2))
