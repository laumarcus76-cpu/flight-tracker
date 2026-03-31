"""
Flight price tracker entry point.

Usage:
  python main.py          # normal run: fetch prices and send alert if deals found
  python main.py --test   # test run: skip API, send alert with fake deals
"""

import argparse
import os
import sys

from dotenv import load_dotenv

from src.api      import get_cheapest_round_trips, generate_date_pairs
from src.checker  import find_deals
from src.config   import load_config
from src.notifier import send_alert


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Flight price tracker")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Send a test alert with fake data; skips the SerpAPI call",
    )
    args = parser.parse_args()

    # ── Load config ────────────────────────────────────────────────────────────
    config = load_config()

    # ── Resolve secrets ────────────────────────────────────────────────────────
    serpapi_key    = os.environ.get("SERPAPI_KEY", "")
    resend_api_key = os.environ.get("RESEND_API_KEY", "")
    alert_email    = os.environ.get("ALERT_EMAIL", "")

    if not resend_api_key:
        sys.exit("Error: RESEND_API_KEY environment variable is not set.")
    if not alert_email:
        sys.exit("Error: ALERT_EMAIL environment variable is not set.")

    # ── Test mode: skip SerpAPI, inject fake deals ─────────────────────────────
    if args.test:
        print(f"[TEST MODE] Sending test digest to {alert_email}")
        fake_deals = {
            "SFO → LAS": [
                {"depart_date": "2026-04-11", "return_date": "2026-04-13",
                 "price": 99.0, "airline": "Southwest",
                 "link": "https://www.google.com/travel/flights"},
            ],
            "OAK → LAS": [
                {"depart_date": "2026-04-09", "return_date": "2026-04-13",
                 "price": 112.0, "airline": "Frontier",
                 "link": "https://www.google.com/travel/flights"},
            ],
        }
        send_alert(
            deals_by_route=fake_deals,
            recipient_email=alert_email,
            api_key=resend_api_key,
            test_mode=True,
        )
        print("[TEST MODE] Done.")
        return

    # ── Normal mode ────────────────────────────────────────────────────────────
    if not serpapi_key:
        sys.exit("Error: SERPAPI_KEY environment variable is not set.")

    date_pairs = generate_date_pairs(
        scan_months_ahead=config.scan_months_ahead,
        trip_patterns=config.trip_patterns,
    )
    print(f"Scanning {len(date_pairs)} date pairs across "
          f"{len(config.routes)} route(s)...")

    deals_by_route: dict[str, list[dict]] = {}

    for route in config.routes:
        label = f"{route.origin} → {route.destination}"
        print(f"\n[{label}] Fetching prices...")

        flights = get_cheapest_round_trips(
            origin=route.origin,
            destination=route.destination,
            date_pairs=date_pairs,
            api_key=serpapi_key,
        )
        print(f"[{label}] {len(flights)} result(s) from SerpAPI")

        deals = find_deals(
            flights=flights,
            threshold=config.price_threshold,
            min_price=config.min_price_sanity,
        )
        print(f"[{label}] {len(deals)} deal(s) under ${config.price_threshold:.0f}")
        deals_by_route[label] = deals

    total_deals = sum(len(v) for v in deals_by_route.values())

    if total_deals == 0:
        print("\nNo deals found below threshold. No email sent.")
        return

    print(f"\nSending digest ({total_deals} deal(s) total) to {alert_email}...")
    send_alert(
        deals_by_route=deals_by_route,
        recipient_email=alert_email,
        api_key=resend_api_key,
    )
    print("Done.")


if __name__ == "__main__":
    main()
