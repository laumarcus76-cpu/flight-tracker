"""
Resend.com email client.

Sends a single batched HTML alert email listing all deals found for a route.
No email is sent when the deals list is empty.
"""

import resend


def send_alert(
    deals: list[dict],
    route: dict,
    recipient_email: str,
    api_key: str,
) -> None:
    """
    Send an HTML alert email listing all deals.

    Args:
        deals: list of deal dicts from checker.find_deals(); no-op if empty
        route: dict with keys "origin" and "destination", e.g. {"origin": "SFO", "destination": "LAS"}
        recipient_email: address to send the alert to
        api_key: Resend API key

    Returns:
        None. Raises on API error or invalid key.
    """
    if not deals:
        return

    raise NotImplementedError
