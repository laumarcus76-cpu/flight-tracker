"""
Resend.com email client.

Sends a bi-weekly digest HTML email grouped by route, sorted price-ascending.
No email is sent when all deal lists are empty.
"""

import os
from datetime import date

import resend

# Sender address — must be a verified domain in your Resend account.
# Defaults to Resend's sandbox address for testing.
_DEFAULT_FROM = "onboarding@resend.dev"


def send_alert(
    deals_by_route: dict[str, list[dict]],
    recipient_email: str,
    api_key: str,
    from_address: str | None = None,
    test_mode: bool = False,
) -> None:
    """
    Send a bi-weekly flight digest email grouped by route.

    Args:
        deals_by_route: dict mapping route label (e.g. "SFO → LAS") to list
                        of deal dicts from checker.find_deals().
        recipient_email: address to send the digest to.
        api_key: Resend API key.
        from_address: sender address (must be verified in Resend). Defaults to
                      RESEND_FROM env var, then the Resend sandbox address.
        test_mode: if True, prepends [TEST] to the subject line.

    Returns:
        None. Raises RuntimeError on API/auth errors.
    """
    all_deals = [d for deals in deals_by_route.values() for d in deals]
    if not all_deals:
        return

    resend.api_key = api_key
    sender = from_address or os.environ.get("RESEND_FROM", _DEFAULT_FROM)

    lowest_price = min(d["price"] for d in all_deals)
    subject = f"✈ Flight Digest: SFO/SJC → LAS — cheapest from ${lowest_price:.0f}"
    if test_mode:
        subject = f"[TEST] {subject}"

    html_body = _build_html(deals_by_route, lowest_price)
    text_body = _build_text(deals_by_route, lowest_price)

    params: resend.Emails.SendParams = {
        "from": sender,
        "to": [recipient_email],
        "subject": subject,
        "html": html_body,
        "text": text_body,
    }

    try:
        response = resend.Emails.send(params)
    except Exception as exc:
        msg = str(exc)
        if "api_key" in msg.lower() or "unauthorized" in msg.lower() or "403" in msg:
            raise RuntimeError(
                f"Resend authentication failed: invalid API key. "
                "Check your RESEND_API_KEY environment variable."
            ) from exc
        raise RuntimeError(f"Resend error: {msg}") from exc

    if isinstance(response, dict) and "error" in response:
        raise RuntimeError(f"Resend API error: {response['error']}")


# ── HTML builder ───────────────────────────────────────────────────────────────

def _build_html(deals_by_route: dict[str, list[dict]], lowest_price: float) -> str:
    today = date.today().strftime("%B %d, %Y")
    sections = "".join(_route_section_html(label, deals)
                       for label, deals in deals_by_route.items() if deals)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Flight Digest</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           background: #f5f5f5; margin: 0; padding: 20px; color: #222; }}
    .container {{ max-width: 680px; margin: 0 auto; background: #fff;
                 border-radius: 8px; overflow: hidden;
                 box-shadow: 0 1px 4px rgba(0,0,0,.12); }}
    .header {{ background: #1a56db; color: #fff; padding: 24px 28px; }}
    .header h1 {{ margin: 0; font-size: 22px; }}
    .header p {{ margin: 6px 0 0; opacity: .85; font-size: 14px; }}
    .summary {{ background: #eff6ff; border-left: 4px solid #1a56db;
               padding: 14px 20px; margin: 20px 28px; border-radius: 4px;
               font-size: 15px; }}
    .section {{ padding: 0 28px 24px; }}
    .section h2 {{ font-size: 17px; color: #1a56db; margin: 24px 0 10px;
                  border-bottom: 1px solid #e5e7eb; padding-bottom: 6px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th {{ background: #f3f4f6; text-align: left; padding: 8px 10px;
          font-weight: 600; color: #374151; }}
    td {{ padding: 8px 10px; border-bottom: 1px solid #f3f4f6; vertical-align: middle; }}
    tr:last-child td {{ border-bottom: none; }}
    .price {{ font-weight: 700; color: #16a34a; font-size: 15px; }}
    .book {{ display: inline-block; background: #1a56db; color: #fff !important;
             text-decoration: none; padding: 4px 12px; border-radius: 4px;
             font-size: 13px; }}
    .footer {{ text-align: center; font-size: 12px; color: #9ca3af;
              padding: 16px 28px 24px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>✈ Flight Price Digest</h1>
      <p>Bay Area → Las Vegas &nbsp;·&nbsp; Generated {today}</p>
    </div>
    <div class="summary">
      Cheapest round-trip found: <strong>${lowest_price:.0f}</strong> &nbsp;—&nbsp;
      covering the next 3 months, all airlines.
    </div>
    <div class="section">
      {sections}
    </div>
    <div class="footer">
      Prices are from Google Flights and may change. Always verify before booking.<br>
      Sent by your flight price tracker · Unsubscribe by removing ALERT_EMAIL from GitHub Secrets.
    </div>
  </div>
</body>
</html>"""


def _route_section_html(label: str, deals: list[dict]) -> str:
    rows = "".join(_deal_row_html(d) for d in deals)
    return f"""
      <h2>{label}</h2>
      <table>
        <thead>
          <tr>
            <th>Depart</th>
            <th>Return</th>
            <th>Trip type</th>
            <th>Price</th>
            <th>Airline</th>
            <th>Book</th>
          </tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>"""


def _deal_row_html(deal: dict) -> str:
    trip_type = _trip_type(deal["depart_date"], deal["return_date"])
    return (
        f"<tr>"
        f"<td>{deal['depart_date']}</td>"
        f"<td>{deal['return_date']}</td>"
        f"<td>{trip_type}</td>"
        f"<td class='price'>${deal['price']:.0f}</td>"
        f"<td>{deal['airline']}</td>"
        f"<td><a class='book' href='{deal['link']}'>View</a></td>"
        f"</tr>"
    )


# ── Plain-text builder ─────────────────────────────────────────────────────────

def _build_text(deals_by_route: dict[str, list[dict]], lowest_price: float) -> str:
    today = date.today().strftime("%B %d, %Y")
    lines = [
        f"✈ Flight Price Digest — Bay Area → Las Vegas",
        f"Generated: {today}",
        f"Cheapest round-trip: ${lowest_price:.0f}",
        "",
    ]
    for label, deals in deals_by_route.items():
        if not deals:
            continue
        lines.append(f"── {label} ──")
        lines.append(f"{'Depart':<12} {'Return':<12} {'Type':<22} {'Price':>6}  Airline")
        lines.append("-" * 72)
        for d in deals:
            trip_type = _trip_type(d["depart_date"], d["return_date"])
            lines.append(
                f"{d['depart_date']:<12} {d['return_date']:<12} "
                f"{trip_type:<22} ${d['price']:<5.0f}  {d['airline']}"
            )
            lines.append(f"  Book: {d['link']}")
        lines.append("")
    lines.append("Prices are from Google Flights and may change. Verify before booking.")
    return "\n".join(lines)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _trip_type(depart_date: str, return_date: str) -> str:
    delta = (date.fromisoformat(return_date) - date.fromisoformat(depart_date)).days
    if delta == 2:
        return "Weekend (Fri–Sun)"
    if delta == 4:
        return "Long Weekend (Thu–Mon)"
    return f"{delta}-day trip"
