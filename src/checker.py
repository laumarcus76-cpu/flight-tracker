"""
Price comparison logic.

Filters raw flight results down to actionable deals:
- removes prices above the threshold
- removes suspiciously low prices (bad data)
- deduplicates by (depart_date, return_date), keeping lowest price
- sorts by price ascending
"""


def find_deals(
    flights: list[dict],
    threshold: float,
    min_price: float = 10.0,
) -> list[dict]:
    """
    Filter and sort flights into actionable deals.

    Args:
        flights: list of flight dicts from api.get_cheapest_round_trips()
        threshold: max price in USD to include (inclusive)
        min_price: min price in USD; below this is treated as bad data

    Returns:
        Filtered, deduplicated, price-ascending list of flight dicts.
    """
    raise NotImplementedError
