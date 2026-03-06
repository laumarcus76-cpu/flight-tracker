# Flight Price Tracker — Project Plan

## Overview

A lightweight personal tool that monitors SFO and SJC → Las Vegas (LAS) flights and sends
a bi-weekly email digest showing the cheapest round-trip options across the next 3 months.
It runs entirely in the cloud on a cron schedule using GitHub Actions — no home server or
always-on machine required.

**Scope:** SFO → LAS and SJC → LAS only. Reverse direction (LAS → Bay Area) is out of scope
to stay within the SerpAPI free tier (250 searches/month).

**Trip patterns checked:** Friday → Sunday (weekend) and Friday → Monday (long weekend).

**Core value:** Receive a bi-weekly email showing every cheap round-trip option from both
Bay Area airports for the next 3 months — sorted by price, covering all airlines including
Southwest, Frontier, Spirit, and Allegiant.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        GitHub Actions                           │
│                                                                 │
│   cron: 0 13 1,15 * *  (1st and 15th of each month, 1pm UTC)   │
│         │                                                       │
│         ▼                                                       │
│   runner checks out repo                                        │
│         │                                                       │
│         ▼                                                       │
│   injects secrets from GitHub Secrets                           │
│   (SERPAPI_KEY, RESEND_API_KEY, ALERT_EMAIL)                    │
│         │                                                       │
│         ▼                                                       │
│   python main.py                                                │
└────────────────────┬────────────────────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          │                     │
          ▼                     ▼
┌──────────────────┐   ┌──────────────────────────┐
│ SerpAPI          │   │   config.yaml             │
│ Google Flights   │   │                           │
│                  │   │  routes:                  │
│  For each route  │   │    - origin: SFO          │
│  × date pair:    │   │      destination: LAS     │
│                  │   │    - origin: SJC          │
│  Call 1:         │   │      destination: LAS     │
│  outbound search │   │                           │
│  → departure_    │   │  price_threshold: 150     │
│    token         │   │  scan_months_ahead: 3     │
│                  │   │  trip_patterns:           │
│  Call 2:         │   │    - [Friday, Sunday]     │
│  return search   │   │    - [Friday, Monday]     │
│  using token     │   └──────────────────────────┘
│  → combined      │
│    round-trip    │
│    price         │
│                  │
│  All carriers:   │
│  SW, Frontier,   │
│  Spirit,         │
│  Allegiant, etc. │
└────────┬─────────┘
         │
         ▼
  price comparison logic
  (filter < threshold,
   reject bad data < $10,
   deduplicate by date pair,
   sort by price ascending)
         │
         ├─── no deals found ──► exit 0 (no email sent)
         │
         ▼
  format bi-weekly digest
  (all deals grouped by route,
   sorted price-ascending,
   deep-link to booking)
         │
         ▼
┌─────────────────────┐
│   Resend.com API    │
│                     │
│  POST /emails       │
│  HTML digest with   │
│  all routes/deals   │
│  sent to            │
│  ALERT_EMAIL        │
└─────────────────────┘
```

---

## Tech Stack

| Component          | Tool / Service           | Notes                                             |
|--------------------|--------------------------|---------------------------------------------------|
| Language           | Python 3.11+             |                                                   |
| Flight data        | SerpAPI (Google Flights) | Free: 250 searches/month; real-time, all carriers |
| Email delivery     | Resend.com               | Free tier: 3,000 emails/month                     |
| Scheduling / CI    | GitHub Actions           | Free for public repos                             |
| Secrets management | GitHub Secrets           | Injected as env vars at runtime                   |
| Configuration      | config.yaml              | Versioned in repo, no code changes needed         |

---

## API Call Budget

| Variable                        | Value                  |
|---------------------------------|------------------------|
| Routes                          | 2 (SFO→LAS, SJC→LAS)  |
| Trip patterns                   | 2 (Fri-Sun, Fri-Mon)   |
| Fridays in a 3-month window     | ~13                    |
| Date pairs per route            | ~26 (13 × 2 patterns)  |
| API calls per date pair         | 2 (two-call flow)      |
| **Calls per run**               | **~104**               |
| Runs per month                  | 2 (1st and 15th)       |
| **Total calls per month**       | **~208**               |
| SerpAPI free tier               | 250/month              |
| **Headroom**                    | **~42 calls (~17%)**   |

> **Note:** If the 3-month window falls on a month boundary with extra Fridays, the per-run
> call count may reach ~112 (224/month). Still within the 250 free tier. The config allows
> reducing `scan_months_ahead` to 2 if needed.

---

## SerpAPI Two-Call Round-Trip Flow

Fetching a round-trip price requires two sequential API calls per (origin, destination, date-pair):

1. **Call 1 — Outbound search:**
   ```
   GET https://serpapi.com/search
   ?engine=google_flights
   &departure_id=SFO
   &arrival_id=LAS
   &outbound_date=2026-04-11    ← Friday
   &return_date=2026-04-13      ← Sunday (or Monday for long weekend)
   &type=1                      ← round trip
   &currency=USD
   &api_key=SERPAPI_KEY
   ```
   Returns outbound itineraries. Each includes a `departure_token`.

2. **Call 2 — Return + combined price:**
   ```
   GET https://serpapi.com/search
   ?engine=google_flights
   &departure_id=SFO
   &arrival_id=LAS
   &outbound_date=2026-04-11
   &return_date=2026-04-13
   &type=1
   &departure_token=<token_from_call_1>
   &currency=USD
   &api_key=SERPAPI_KEY
   ```
   Returns return itineraries with the **combined round-trip price** for each pairing.

---

## Ticket Status Legend

| Symbol | Meaning     |
|--------|-------------|
| [ ]    | Not started |
| [x]    | Complete    |
| [~]    | In progress |

---

## Tickets

---

### TICKET-001 — Project Setup

- **Status:** [x]
- **Complexity:** Low
- **Depends on:** Nothing

**Purpose**

Establish the repository structure, dependency management, and guardrails so all subsequent
tickets have a clean foundation to build on.

**Tasks**

- [x] Create repo directory layout:
  ```
  flight-tracker/
  ├── .github/
  │   └── workflows/
  │       └── check_prices.yml
  ├── src/
  │   ├── __init__.py
  │   ├── api.py          # SerpAPI Google Flights client
  │   ├── checker.py      # price comparison logic
  │   ├── notifier.py     # Resend email client
  │   └── config.py       # config loader
  ├── tests/
  │   └── test_checker.py
  ├── config.yaml         # user-editable settings (gitignored)
  ├── config.example.yaml # committed template with comments
  ├── requirements.txt
  ├── .gitignore
  ├── README.md
  └── main.py             # entry point
  ```
- [x] Add `requirements.txt` with pinned versions: `google-search-results`, `pyyaml`, `resend`, `python-dotenv`, `pytest`
- [x] Add `.gitignore` covering: `__pycache__/`, `*.pyc`, `.env`, `config.yaml`
- [x] Add `config.example.yaml` with all fields documented inline
- [x] Verify `python -m pip install -r requirements.txt` runs without errors

**Acceptance Criteria**

- [x] Running `pip install -r requirements.txt` in a clean virtual environment succeeds
- [x] `python main.py` runs without import errors (even if it does nothing yet)
- [x] No secrets, `.env` files, or personal data are committed to the repo
- [x] Directory structure matches the layout above

---

### TICKET-002 — SerpAPI Google Flights Integration

- **Status:** [x]
- **Complexity:** Medium
- **Depends on:** TICKET-001

**Purpose**

Build the module that fetches real-time round-trip flight prices from Google Flights via
SerpAPI. Scans all Friday → Sunday and Friday → Monday date pairs within a rolling 3-month
window from the run date, for both SFO → LAS and SJC → LAS. Returns the cheapest combined
round-trip price per date pair from all carriers.

**SerpAPI account setup:**
- Sign up at https://serpapi.com (free, instant, no approval)
- Free tier: 250 searches/month
- API key available immediately in the dashboard

**Tasks**

- [ ] Sign up for SerpAPI and obtain an API key
- [ ] Read the [SerpAPI Google Flights docs](https://serpapi.com/google-flights-api) and
      confirm the two-call round-trip flow
- [ ] Implement `src/api.py`:
  - `get_cheapest_round_trips(origin, destination, date_pairs, api_key)` function
    - `date_pairs`: list of `(depart_date, return_date)` tuples as `"YYYY-MM-DD"` strings
    - For each date pair: Call 1 (outbound) → extract cheapest `departure_token` → Call 2
      (return with token) → extract cheapest combined round-trip price
    - Sleeps 0.5s between date pairs to respect rate limits
    - Handles HTTP errors and non-200 responses with descriptive exceptions
    - Returns a list of dicts:
      ```python
      [
        {
          "depart_date": "2026-04-11",
          "return_date": "2026-04-13",
          "price": 118.0,
          "airline": "Southwest",
          "link": "https://www.google.com/flights/..."
        }
      ]
      ```
  - `generate_date_pairs(scan_months_ahead, trip_patterns)` helper
    - Computes a rolling window: today → today + `scan_months_ahead` months
    - Finds all Fridays in that window
    - For each Friday, generates one date pair per trip pattern:
      - `("Friday", "Sunday")` → depart_date=Friday, return_date=Friday+2
      - `("Friday", "Monday")` → depart_date=Friday, return_date=Friday+3
    - Skips any departure date in the past or within 3 days of today
    - Returns sorted list of `(depart_date_str, return_date_str)` tuples
- [ ] Add a `__main__` block for quick manual testing: `python -m src.api`

**Acceptance Criteria**

- [ ] `get_cheapest_round_trips("SFO", "LAS", [("2026-04-11", "2026-04-13")], key)` returns
      a non-empty list when Google Flights has results
- [ ] Function raises a clear exception when the API key is invalid
- [ ] Function returns an empty list (not an error) when no flights are found for a date pair
- [ ] `generate_date_pairs(3, [("Friday","Sunday"),("Friday","Monday")])` returns ~26 pairs
      covering the next 3 months
- [ ] No past dates appear in the generated date pairs
- [ ] Manual test (`python -m src.api`) prints results to stdout without crashing
- [ ] Both SFO and SJC work as valid origin inputs

---

### TICKET-003 — Price Comparison Logic

- **Status:** [x]
- **Complexity:** Medium
- **Depends on:** TICKET-002

**Purpose**

Filter the raw API results down to actionable deals. Applies the price threshold, rejects
data anomalies, deduplicates, and sorts so the digest email is clean and ranked by value.

**Tasks**

- [ ] Implement `src/checker.py`:
  - `find_deals(flights, threshold, min_price=10)` function
  - Filters out prices above `threshold`
  - Filters out prices below `min_price` (catches obviously bad data; default $10)
  - Deduplicates by `(depart_date, return_date)` — keeps lowest price per date pair
  - Sorts results by price ascending
  - Returns filtered, sorted list
- [ ] Write unit tests in `tests/test_checker.py`:
  - Test: normal deal is returned
  - Test: price above threshold is excluded
  - Test: suspiciously low price (below min_price) is excluded
  - Test: duplicate date pairs are deduplicated, keeping lowest price
  - Test: empty input returns empty list
  - Test: price exactly at threshold is included
  - Test: price $1 above threshold is excluded

**Acceptance Criteria**

- [ ] `python -m pytest tests/test_checker.py` passes with all tests green
- [ ] A flight at exactly the threshold price ($150.00) is included (boundary condition)
- [ ] A flight at $151 is excluded
- [ ] A flight at $9 is excluded when min_price is $10
- [ ] Duplicate routes on same dates retain only the cheaper option

---

### TICKET-004 — Resend Email Digest

- **Status:** [x]
- **Complexity:** Medium
- **Depends on:** TICKET-003

**Purpose**

Send a formatted HTML bi-weekly digest email listing all deals found across both routes,
grouped by route, sorted by price. The email gives an at-a-glance view of the cheapest
options for the next 3 months from both Bay Area airports.

**Tasks**

- [ ] Sign up for Resend.com and obtain an API key
- [ ] Verify a sender domain or use the Resend sandbox address for testing
- [ ] Implement `src/notifier.py`:
  - `send_alert(deals_by_route, recipient_email, api_key)` function
    - `deals_by_route`: dict mapping route label (e.g. `"SFO → LAS"`) to list of deal dicts
    - Builds an HTML email with one section per route
    - Each section: sorted price-ascending table of deals with columns:
      Departure date | Return date | Trip type | Price | Airline | Book
    - Trip type column shows "Weekend (Fri-Sun)" or "Long Weekend (Fri-Mon)"
    - Subject line: `✈ Flight Digest: SFO/SJC → LAS — cheapest from $XX` (lowest price across all routes)
    - Guard clause: returns early (no API call) if all deal lists are empty
  - Plain-text fallback body listing deals in a readable format
- [ ] Add a plain-text fallback body

**Acceptance Criteria**

- [ ] Email renders a readable grouped table in Gmail and Apple Mail
- [ ] Subject line uses the lowest price found across all routes
- [ ] Each route section is clearly labeled and sorted price-ascending
- [ ] Trip type (Fri-Sun vs Fri-Mon) is visible per row
- [ ] Function is a no-op when all deal lists are empty
- [ ] Invalid API key raises a clear exception

---

### TICKET-005 — GitHub Actions Workflow

- **Status:** [ ]
- **Complexity:** Medium
- **Depends on:** TICKET-001, TICKET-002, TICKET-004

**Purpose**

Wire everything together so the script runs automatically on the 1st and 15th of each month.

**Tasks**

- [ ] Update `.github/workflows/check_prices.yml`:
  - Trigger: `schedule` (cron) + `workflow_dispatch` (manual trigger)
  - Cron: `0 13 1,15 * *` (1st and 15th of each month at 1pm UTC / ~5-6am Pacific)
  - Runner: `ubuntu-latest`
  - Steps:
    1. Checkout repo
    2. Set up Python 3.11
    3. Install dependencies from `requirements.txt`
    4. Run `python main.py`
  - Inject secrets as environment variables:
    - `SERPAPI_KEY` → from GitHub Secret
    - `RESEND_API_KEY` → from GitHub Secret
    - `ALERT_EMAIL` → from GitHub Secret
- [ ] Add secrets to the GitHub repo (Settings → Secrets and variables → Actions)
- [ ] Test via `workflow_dispatch` before relying on the cron schedule

**Acceptance Criteria**

- [ ] Workflow file passes YAML lint
- [ ] Manual trigger (`workflow_dispatch`) runs successfully end-to-end
- [ ] Workflow completes in under 3 minutes on a normal run
- [ ] Cron fires on the 1st and 15th (verify via Actions tab)
- [ ] Secrets are never printed to workflow logs
- [ ] Non-zero Python exit code marks the workflow run as failed

---

### TICKET-006 — Configuration System

- **Status:** [ ]
- **Complexity:** Low
- **Depends on:** TICKET-001

**Purpose**

All user-tunable settings live in `config.yaml`. Changing routes, threshold, scan window,
or trip patterns requires no code changes.

**Tasks**

- [ ] Define final `config.example.yaml` schema:
  ```yaml
  routes:
    - origin: SFO
      destination: LAS
    - origin: SJC
      destination: LAS

  price_threshold: 150       # Max round-trip price in USD to include in digest
  min_price_sanity: 10       # Ignore prices below this (likely bad data)

  scan_months_ahead: 3       # How many months ahead to scan from today's date
                             # Keep at 3 to stay within SerpAPI 250/month free tier

  trip_patterns:             # Day-of-week pairs to check
    - [Friday, Sunday]       # Weekend trip (2 nights)
    - [Friday, Monday]       # Long weekend (3 nights)
  ```
- [ ] Implement `src/config.py`:
  - `load_config(path="config.yaml")` function
  - Validates required fields; raises `ValueError` with a clear message if missing
  - Returns validated `Config` dataclass
- [ ] Update `main.py` to load config and pass values to all modules

**Acceptance Criteria**

- [ ] Adding a route to `config.yaml` causes it to be checked with no code changes
- [ ] Reducing `scan_months_ahead` to 2 correctly shrinks the date pairs scanned
- [ ] Adding `[Saturday, Monday]` to `trip_patterns` causes Sat→Mon pairs to be generated
- [ ] Missing required field raises `ValueError` naming the missing field
- [ ] `config.example.yaml` is committed with inline comments on every field

---

### TICKET-007 — Manual Test Mode

- **Status:** [ ]
- **Complexity:** Low
- **Depends on:** TICKET-004, TICKET-005, TICKET-006

**Purpose**

Verify the full email pipeline works without waiting for the cron and without needing real
cheap flights to exist.

**Tasks**

- [ ] Add a `--test` flag to `main.py`:
  - Skips the SerpAPI call entirely
  - Injects fake deals for both routes:
    ```python
    {
      "SFO → LAS": [{"depart_date":"2026-04-11","return_date":"2026-04-13","price":99,"airline":"Southwest","link":"https://example.com"}],
      "SJC → LAS": [{"depart_date":"2026-04-11","return_date":"2026-04-14","price":112,"airline":"Frontier","link":"https://example.com"}]
    }
    ```
  - Prints `[TEST MODE] Sending test digest to <email>` to stdout
- [ ] Document the flag in the README
- [ ] Expose `test_mode` boolean input on `workflow_dispatch` in the workflow YAML

**Acceptance Criteria**

- [ ] `python main.py --test` sends a real email with fake deal data for both routes
- [ ] Subject line includes `[TEST]`
- [ ] No SerpAPI calls are made in test mode
- [ ] `workflow_dispatch` with `test_mode: true` passes `--test` to the script

---

### TICKET-008 — Documentation

- **Status:** [ ]
- **Complexity:** Low
- **Depends on:** All other tickets

**Tasks**

- [ ] Write `README.md` covering:
  - [ ] **What it does** — 2-3 sentence description
  - [ ] **Prerequisites** — Python 3.11+, GitHub account, SerpAPI account, Resend account
  - [ ] **Account setup** — SerpAPI (where to find key, free tier limits) and Resend (sender verification, key)
  - [ ] **Configuration** — copy `config.example.yaml` to `config.yaml`, edit routes/threshold/scan window
  - [ ] **SerpAPI call budget** — explain 250/month limit and why `scan_months_ahead: 3` is the safe default
  - [ ] **GitHub Secrets setup** — exact names: `SERPAPI_KEY`, `RESEND_API_KEY`, `ALERT_EMAIL`
  - [ ] **Running locally** — `pip install -r requirements.txt` → `python main.py --test`
  - [ ] **Verifying the workflow** — `workflow_dispatch`, where to check logs
  - [ ] **Cron schedule** — explain `0 13 1,15 * *`, link to crontab.guru
  - [ ] **Troubleshooting** — bad API key, Resend sender not verified, no flights found, exceeding SerpAPI limit

**Acceptance Criteria**

- [ ] All three secret names in README exactly match the workflow YAML
- [ ] README explains the bi-weekly schedule and call budget clearly
- [ ] Troubleshooting covers at least 3 failure scenarios
- [ ] A new reader can go from zero to running in under 30 minutes

---

## Suggested Build Order

```
TICKET-001  (setup) ✅
     │
     ├──► TICKET-006  (config)
     │
     ├──► TICKET-002  (SerpAPI integration) ✅
     │         │
     │         └──► TICKET-003  (price logic) ✅
     │                   │
     │                   └──► TICKET-004  (email digest) ✅
     │                             │
     └──────────────────────────── └──► TICKET-005  (GitHub Actions)
                                             │
                                        TICKET-007  (test mode)
                                             │
                                        TICKET-008  (docs)
```

---

## Open Questions

- [x] ~~Travelpayouts vs SerpAPI~~ — **Resolved: SerpAPI.**
- [x] ~~Daily vs weekly vs bi-weekly~~ — **Resolved: bi-weekly (1st and 15th), SFO/SJC→LAS only.**
- [x] ~~Which trip patterns~~ — **Resolved: Fri→Sun (weekend) and Fri→Mon (long weekend).**
- [x] ~~How far ahead to scan~~ — **Resolved: 3 months rolling window from run date.**
- [ ] Should the digest send even if no deals are below threshold, showing the cheapest
      available regardless? (Current plan: only send if deals exist below threshold)
- [ ] What should happen if SerpAPI returns no results for a date pair?
      (Current plan: log a warning, continue to next pair, do not error)

---

## API Reference

### SerpAPI Google Flights

- **Docs:** https://serpapi.com/google-flights-api
- **Base URL:** `https://serpapi.com/search`
- **Auth:** `api_key` query parameter
- **Free tier:** 250 searches/month, instant signup
- **Python package:** `google-search-results` (`pip install google-search-results`)

**Key parameters:**

| Parameter         | Value / Example   | Notes                                     |
|-------------------|-------------------|-------------------------------------------|
| `engine`          | `google_flights`  | Required                                  |
| `departure_id`    | `SFO`             | IATA code                                 |
| `arrival_id`      | `LAS`             | IATA code                                 |
| `outbound_date`   | `2026-04-11`      | YYYY-MM-DD (a Friday)                     |
| `return_date`     | `2026-04-13`      | YYYY-MM-DD (Sunday or Monday)             |
| `type`            | `1`               | 1 = round trip, 2 = one way              |
| `currency`        | `USD`             |                                           |
| `departure_token` | `<from call 1>`   | Only on Call 2; triggers combined pricing |
| `api_key`         | `SERPAPI_KEY`     | From env var                              |

### Resend

- **Docs:** https://resend.com/docs
- **Python package:** `resend` (`pip install resend`)
- **Free tier:** 3,000 emails/month

---

*Last updated: 2026-03-06*
