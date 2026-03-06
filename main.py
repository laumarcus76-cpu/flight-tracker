"""
Flight price tracker entry point.

Usage:
  python main.py          # normal run: fetch prices and send alert if deals found
  python main.py --test   # test run: skip API, send alert with fake deal
"""

import argparse
import os
import sys

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Flight price tracker")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Send a test alert with fake data; skips the SerpAPI call",
    )
    args = parser.parse_args()

    # Implemented in TICKET-006
    # config = load_config()

    # Implemented in TICKET-002
    # flights = get_cheapest_round_trips(...)

    # Implemented in TICKET-003
    # deals = find_deals(...)

    # Implemented in TICKET-004
    # send_alert(...)


if __name__ == "__main__":
    main()
