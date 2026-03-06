"""
SerpAPI Google Flights client.

Two-call round-trip flow per date pair:
  Call 1: outbound search → picks cheapest option's departure_token
  Call 2: return search using departure_token → extracts combined round-trip price

Usage:
  python -m src.api
"""

import os
import time
from calendar import monthrange
from datetime import date, timedelta

from serpapi import GoogleSearch

# Weekday name → Python weekday int (Monday=0 … Sunday=6)
_WEEKDAY = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}

# Minimum days from today before a departure date is considered
_MIN_DAYS_OUT = 3


def generate_date_pairs(
    scan_months_ahead: int,
    trip_patterns: list[list[str]] | None = None,
) -> list[tuple[str, str]]:
    """
    Generate (depart_date, return_date) pairs for the rolling scan window.

    Finds every occurrence of the depart weekday in the window and pairs it
    with the next occurrence of the return weekday.

    Args:
        scan_months_ahead: how many months ahead from today to scan
        trip_patterns: list of [depart_weekday, return_weekday] pairs.
                       Defaults to [["Friday","Sunday"], ["Friday","Monday"]]

    Returns:
        Sorted, deduplicated list of ("YYYY-MM-DD", "YYYY-MM-DD") tuples.
    """
    if trip_patterns is None:
        trip_patterns = [["Friday", "Sunday"], ["Friday", "Monday"]]

    today = date.today()
    min_depart = today + timedelta(days=_MIN_DAYS_OUT)

    # Compute end of scan window: same day-of-month, N months ahead
    # e.g. March 6 + 3 months = June 6 (not June 30), giving ~13 Fridays
    raw_end_month = today.month + scan_months_ahead
    end_year = today.year + (raw_end_month - 1) // 12
    end_month = ((raw_end_month - 1) % 12) + 1
    # Clamp day to the last valid day of end_month (handles e.g. Jan 31 + 1 month)
    end_day = min(today.day, monthrange(end_year, end_month)[1])
    end_date = date(end_year, end_month, end_day)

    pairs: set[tuple[str, str]] = set()

    for depart_day_name, return_day_name in trip_patterns:
        depart_wd = _WEEKDAY[depart_day_name]
        return_wd = _WEEKDAY[return_day_name]

        # Advance to the first matching depart weekday on or after min_depart
        days_ahead = (depart_wd - min_depart.weekday()) % 7
        current_depart = min_depart + timedelta(days=days_ahead)

        while current_depart <= end_date:
            # Next occurrence of return_weekday after current_depart
            days_to_return = (return_wd - current_depart.weekday()) % 7
            if days_to_return == 0:
                days_to_return = 7  # return must be after depart
            return_dt = current_depart + timedelta(days=days_to_return)

            if return_dt <= end_date:
                pairs.add(
                    (
                        current_depart.strftime("%Y-%m-%d"),
                        return_dt.strftime("%Y-%m-%d"),
                    )
                )

            current_depart += timedelta(weeks=1)

    return sorted(pairs)


def get_cheapest_round_trips(
    origin: str,
    destination: str,
    date_pairs: list[tuple[str, str]],
    api_key: str,
) -> list[dict]:
    """
    Fetch the cheapest round-trip fares for each (depart_date, return_date) pair.

    For each date pair:
      - Call 1: outbound search; selects the departure_token from the cheapest result
      - Call 2: return search using that token; extracts the cheapest combined price

    Args:
        origin: IATA code, e.g. "SFO"
        destination: IATA code, e.g. "LAS"
        date_pairs: list of ("YYYY-MM-DD", "YYYY-MM-DD") tuples
        api_key: SerpAPI key

    Returns:
        List of dicts with keys: depart_date, return_date, price, airline, link.
        Returns empty list when no results are found.

    Raises:
        RuntimeError: on SerpAPI errors (includes invalid key message)
    """
    results = []

    base_params = {
        "engine": "google_flights",
        "departure_id": origin,
        "arrival_id": destination,
        "type": "1",       # round trip
        "currency": "USD",
        "hl": "en",
        "gl": "us",
        "api_key": api_key,
    }

    for depart_date, return_date in date_pairs:
        params = {
            **base_params,
            "outbound_date": depart_date,
            "return_date": return_date,
        }

        # ── Call 1: outbound search ────────────────────────────────────────
        data = GoogleSearch(params).get_dict()
        _check_error(data, call=1, origin=origin, destination=destination,
                     depart_date=depart_date)

        outbound_options = data.get("best_flights", []) + data.get("other_flights", [])
        outbound_with_token = [f for f in outbound_options if f.get("departure_token")]

        if not outbound_with_token:
            print(f"  [skip] no outbound results for {origin}→{destination} "
                  f"{depart_date}→{return_date}")
            time.sleep(0.5)
            continue

        # Pick the departure_token from the cheapest outbound option
        cheapest_out = min(outbound_with_token,
                           key=lambda f: f.get("price", float("inf")))
        departure_token = cheapest_out["departure_token"]

        time.sleep(0.5)

        # ── Call 2: return search with departure_token ─────────────────────
        data2 = GoogleSearch({**params, "departure_token": departure_token}).get_dict()
        _check_error(data2, call=2, origin=origin, destination=destination,
                     depart_date=depart_date)

        return_options = data2.get("best_flights", []) + data2.get("other_flights", [])

        if not return_options:
            print(f"  [skip] no return results for {origin}→{destination} "
                  f"{depart_date}→{return_date}")
            time.sleep(0.5)
            continue

        cheapest_ret = min(return_options,
                           key=lambda f: f.get("price", float("inf")))
        price = cheapest_ret.get("price")

        if price is None:
            time.sleep(0.5)
            continue

        # Airline from the first leg of the cheapest return itinerary
        legs = cheapest_ret.get("flights", [])
        airline = legs[0].get("airline", "Unknown") if legs else "Unknown"

        # Google Flights search link (opens pre-filled search; not a booking deep-link)
        link = _google_flights_link(origin, destination, depart_date, return_date)

        results.append(
            {
                "depart_date": depart_date,
                "return_date": return_date,
                "price": float(price),
                "airline": airline,
                "link": link,
            }
        )

        time.sleep(0.5)

    return results


# ── Helpers ────────────────────────────────────────────────────────────────────

def _check_error(data: dict, *, call: int, origin: str, destination: str,
                 depart_date: str) -> None:
    """Raise RuntimeError with a descriptive message if SerpAPI returned an error."""
    if "error" in data:
        error_msg = data["error"]
        if "Invalid API key" in error_msg or "api_key" in error_msg.lower():
            raise RuntimeError(
                f"SerpAPI authentication failed (Call {call}): invalid API key. "
                "Check your SERPAPI_KEY environment variable."
            )
        raise RuntimeError(
            f"SerpAPI error (Call {call}, {origin}→{destination} {depart_date}): "
            f"{error_msg}"
        )


def _google_flights_link(origin: str, destination: str,
                          depart_date: str, return_date: str) -> str:
    """Return a Google Flights search URL pre-filled with the route and dates."""
    return (
        f"https://www.google.com/travel/flights/search"
        f"?tfs=CBwQAhoeEgoyMDI2LTA0LTExagcIARIDU0ZPcgcIARIDTEFT"
        f"#flt={origin}.{destination}.{depart_date}"
        f"*{destination}.{origin}.{return_date};c:USD;e:1;sd:1;t:f"
    )


# ── Manual test entrypoint ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    api_key = os.environ.get("SERPAPI_KEY", "")
    if not api_key:
        raise SystemExit("SERPAPI_KEY environment variable is not set.")

    print("Generating date pairs (3 months, Fri-Sun + Fri-Mon)...")
    pairs = generate_date_pairs(3, [["Friday", "Sunday"], ["Friday", "Monday"]])
    print(f"Generated {len(pairs)} date pairs. First 4: {pairs[:4]}\n")

    print("Fetching SFO → LAS (first 2 date pairs)...")
    results = get_cheapest_round_trips("SFO", "LAS", pairs[:2], api_key)
    print(json.dumps(results, indent=2))
