# Flight Price Tracker

A lightweight personal tool that monitors SFO and OAK → Las Vegas (LAS) flights and sends
a bi-weekly email digest of the cheapest round-trip options across the next 3 months.
Runs entirely on GitHub Actions — no server required.

**Trip patterns:** Friday → Sunday (weekend) and Thursday → Monday (long weekend).
**Alert threshold:** $150 round-trip (configurable).
**Schedule:** 1st and 15th of each month, automatically.

---

## How It Works

1. GitHub Actions wakes up on the 1st and 15th of each month
2. Fetches real-time prices from Google Flights via SerpAPI for both SFO→LAS and OAK→LAS
3. Filters deals below your price threshold
4. Sends a grouped HTML digest email via Resend if any deals are found

---

## Prerequisites

- Python 3.11+
- A [GitHub](https://github.com) account (free)
- A [SerpAPI](https://serpapi.com) account (free tier: 250 searches/month)
- A [Resend](https://resend.com) account (free tier: 3,000 emails/month)

---

## Account Setup

### SerpAPI

1. Sign up at [serpapi.com](https://serpapi.com) — instant, no approval required
2. Go to **Dashboard → API Key** and copy your key
3. Free tier: 250 searches/month (this tool uses ~208/month with default settings)

### Resend

1. Sign up at [resend.com](https://resend.com)
2. Go to **API Keys → Create API Key** and copy your key
3. **Sender domain:** by default the tool sends from `onboarding@resend.dev` (Resend's
   sandbox address). To use your own `from` address, verify a domain under
   **Domains** in the Resend dashboard and set the `RESEND_FROM` environment variable.

---

## Configuration

Copy the example config and edit it:

```bash
cp config.example.yaml config.yaml
```

```yaml
routes:
  - origin: SFO
    destination: LAS
  - origin: OAK
    destination: LAS

price_threshold: 150       # max round-trip price in USD to include in digest
min_price_sanity: 10       # ignore prices below this (likely bad data)
scan_months_ahead: 3       # how many months ahead to scan (keep at 3 for free tier)

trip_patterns:
  - [Friday, Sunday]       # weekend trip (2 nights)
  - [Thursday, Monday]     # long weekend (4 nights)
```

> `config.yaml` contains no secrets and is safe to commit.
> Do not add your email address or API keys to this file.

### SerpAPI call budget

The free tier allows 250 searches/month. Default settings use ~208:

```
24 date pairs × 2 routes × 2 calls per pair × 2 runs/month = 208 calls/month
```

If you add more routes or patterns, reduce `scan_months_ahead` to stay within the limit.

---

## GitHub Secrets Setup

In your GitHub repo go to **Settings → Secrets and variables → Actions** and add:

| Secret name       | Value                        |
|-------------------|------------------------------|
| `SERPAPI_KEY`     | Your SerpAPI API key         |
| `RESEND_API_KEY`  | Your Resend API key          |
| `ALERT_EMAIL`     | Email address to notify      |

These are injected as environment variables at runtime and never appear in logs.

---

## Running Locally

```bash
# Install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copy and edit config
cp config.example.yaml config.yaml

# Create .env with your keys
echo "SERPAPI_KEY=your_key_here" >> .env
echo "RESEND_API_KEY=your_key_here" >> .env
echo "ALERT_EMAIL=you@example.com" >> .env

# Send a test email with fake data (0 SerpAPI calls)
python main.py --test

# Run a real scan (uses ~96 SerpAPI calls)
python main.py
```

---

## Verifying the GitHub Actions Workflow

1. Push your code to GitHub
2. Go to your repo → **Actions** → **Check Flight Prices** → **Run workflow**
3. To test without using SerpAPI credits, toggle **"Send a test alert with fake data"** to ON
4. Click **Run workflow** and watch the logs in real time

A successful run will show each route being fetched and either:
- `Sending digest (N deal(s) total) to your@email.com` — email sent
- `No deals found below threshold. No email sent.` — no deals, no email

---

## Cron Schedule

The workflow runs on this cron: `0 13 1,15 * *`

- **1st and 15th** of every month
- **1:00 PM UTC** (5:00 AM or 6:00 AM Pacific, depending on DST)

To change the schedule, edit `.github/workflows/check_prices.yml`.
Use [crontab.guru](https://crontab.guru) to build and preview cron expressions.

---

## Running Tests

```bash
python -m pytest tests/ -v
```

24 tests covering price filtering, deduplication, date pair generation, and trip type logic.

---

## Troubleshooting

**No email received after a workflow run**
- Check the Actions log for `No deals found below threshold.` — this is normal if no flights
  are under your threshold. Try raising `price_threshold` in `config.yaml` temporarily to
  confirm the email pipeline works.
- Run `python main.py --test` locally to verify Resend is configured correctly.

**`SerpAPI authentication failed: invalid API key`**
- Double-check the `SERPAPI_KEY` secret in GitHub matches your key from the SerpAPI dashboard.
- Make sure there are no leading/trailing spaces in the secret value.

**`Resend authentication failed: invalid API key`**
- Double-check the `RESEND_API_KEY` secret in GitHub.
- Confirm the API key is still active in the Resend dashboard (keys can be revoked).

**Emails arrive from `onboarding@resend.dev` instead of your domain**
- This is expected on the free tier with no verified domain. To use your own sender address,
  verify a domain in Resend and set `RESEND_FROM=alerts@yourdomain.com` as a GitHub Secret.

**Workflow exceeds SerpAPI free tier (250/month)**
- Reduce `scan_months_ahead` from 3 to 2 in `config.yaml` to cut calls to ~160/month.
- Remove one route to halve the call count.
- Upgrade to SerpAPI's Hobby plan ($50/month, 5,000 searches) for more routes and patterns.

**`FileNotFoundError: config.yaml`**
- Make sure `config.yaml` is committed to your repo. It is safe to commit — it contains
  no secrets.

---

## Project Structure

```
flight-tracker/
├── .github/workflows/check_prices.yml  # GitHub Actions cron + dispatch
├── src/
│   ├── api.py        # SerpAPI Google Flights client (two-call round-trip flow)
│   ├── checker.py    # price filtering, deduplication, sorting
│   ├── notifier.py   # Resend HTML email digest
│   └── config.py     # config.yaml loader and validator
├── tests/
│   ├── test_checker.py
│   └── test_api.py
├── config.yaml         # your settings (routes, threshold, patterns)
├── config.example.yaml # template with inline comments
├── requirements.txt
└── main.py             # entry point
```
