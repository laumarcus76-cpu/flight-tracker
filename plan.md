# Flight Price Tracker — Project Plan

## Overview

A lightweight personal tool that monitors SFO and SJC → Las Vegas (LAS) flights and sends
a bi-weekly email digest showing the cheapest round-trip options across the next 3 months.
It runs entirely in the cloud on a cron schedule using GitHub Actions — no home server or
always-on machine required.

**Scope:** SFO → LAS and SJC → LAS only. Reverse direction (LAS → Bay Area) is out of scope
to stay within the SerpAPI free tier (250 searches/month).

**Trip patterns checked:** Friday → Sunday (weekend, 2 nights) and Thursday → Monday (long weekend, 4 nights).

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
│  return search   │   │    - [Thursday, Monday]   │
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
   deep-link to booking via booking_token)
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

| Variable                        | Value                    |
|---------------------------------|--------------------------|
| Routes                          | 2 (SFO→LAS, SJC→LAS)    |
| Trip patterns                   | 2 (Fri-Sun, Thu-Mon)     |
| Departures in a 3-month window  | ~13                      |
| Date pairs per route            | ~26 (13 × 2 patterns)    |
| API calls per date pair         | 2 (two-call flow)        |
| **Calls per run**               | **~104**                 |
| Runs per month                  | 2 (1st and 15th)         |
| **Total calls per month**       | **~208**                 |
| SerpAPI free tier               | 250/month                |
| **Headroom**                    | **~42 calls (~17%)**     |

> **Note:** The scan window anchors to today's date + 3 months (same day-of-month, not
> end-of-month) to keep call counts predictable. Reduce `scan_months_ahead` to 2 if needed.

---

## SerpAPI Two-Call Round-Trip Flow

Fetching a round-trip price requires two sequential API calls per (origin, destination, date-pair):

1. **Call 1 — Outbound search:**
   ```
   GET https://serpapi.com/search
   ?engine=google_flights
   &departure_id=SFO
   &arrival_id=LAS
   &outbound_date=2026-04-10    ← Thursday (or Friday for weekend)
   &return_date=2026-04-13      ← Monday (or Sunday for weekend)
   &type=1                      ← round trip
   &currency=USD
   &api_key=SERPAPI_KEY
   ```
   Returns outbound itineraries. Each includes a `departure_token`.

2. **Call 2 — Return + combined price:**
   ```
   GET https://serpapi.com/search
   ...same params...
   &departure_token=<token_from_call_1>
   ```
   Returns return itineraries with the **combined round-trip price**. Each result includes
   a `booking_token` used to construct the Google Flights deep-link in the email.

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
  │   ├── test_checker.py
  │   └── test_api.py
  ├── config.yaml         # user-editable settings (committed, no secrets)
  ├── config.example.yaml # committed template with comments
  ├── requirements.txt
  ├── .gitignore
  └── main.py             # entry point
  ```
- [x] Add `requirements.txt` with pinned versions: `google-search-results`, `pyyaml`, `resend`, `python-dotenv`, `pytest`
- [x] Add `.gitignore` covering: `__pycache__/`, `*.pyc`, `.env`, `.venv/`
- [x] Add `config.example.yaml` with all fields documented inline
- [x] Verify `python -m pip install -r requirements.txt` runs without errors

**Acceptance Criteria**

- [x] Running `pip install -r requirements.txt` in a clean virtual environment succeeds
- [x] `python main.py` runs without import errors
- [x] No secrets or `.env` files committed to the repo
- [x] Directory structure matches the layout above

---

### TICKET-002 — SerpAPI Google Flights Integration

- **Status:** [x]
- **Complexity:** Medium
- **Depends on:** TICKET-001

**Purpose**

Build the module that fetches real-time round-trip flight prices from Google Flights via
SerpAPI. Scans all Friday → Sunday and Thursday → Monday date pairs within a rolling 3-month
window from the run date, for both SFO → LAS and SJC → LAS.

**Tasks**

- [x] Sign up for SerpAPI and obtain an API key
- [x] Read the SerpAPI Google Flights docs and confirm the two-call round-trip flow
- [x] Implement `src/api.py`:
  - [x] `get_cheapest_round_trips(origin, destination, date_pairs, api_key)`
    - Two-call flow per date pair (outbound → departure_token → return + combined price)
    - Extracts `booking_token` from Call 2 for Google Flights deep-link
    - 0.5s sleep between calls to respect rate limits
    - Descriptive `RuntimeError` on API errors or invalid key
    - Returns `[{depart_date, return_date, price, airline, link}]`
  - [x] `generate_date_pairs(scan_months_ahead, trip_patterns)`
    - Rolling window: today+3 days → today+N months (same day anchor)
    - Finds all Thursday and Friday occurrences in window
    - Generates Thu→Mon (4-day) and Fri→Sun (2-day) pairs
    - Returns sorted, deduplicated list
- [x] Add `__main__` block for manual testing: `python -m src.api`
- [x] Verified with real API call: confirmed two-call flow, booking_token extraction, link construction

**Acceptance Criteria**

- [x] `get_cheapest_round_trips("SFO", "LAS", [...], key)` returns results with real prices
- [x] Function raises a clear `RuntimeError` when the API key is invalid
- [x] Function returns empty list (not an error) when no flights found for a date pair
- [x] `generate_date_pairs(3, [...])` returns ~24 pairs covering the next 3 months
- [x] No past dates appear in generated date pairs
- [x] Both SFO and SJC work as valid origin inputs

---

### TICKET-003 — Price Comparison Logic

- **Status:** [x]
- **Complexity:** Medium
- **Depends on:** TICKET-002

**Purpose**

Filter raw API results down to actionable deals. Applies price threshold, rejects anomalies,
deduplicates, and sorts so the digest is clean and ranked by value.

**Tasks**

- [x] Implement `src/checker.py`:
  - [x] `find_deals(flights, threshold, min_price=10)` function
  - [x] Filters prices above `threshold`
  - [x] Filters prices below `min_price` (bad data guard)
  - [x] Deduplicates by `(depart_date, return_date)`, keeps lowest price per pair
  - [x] Sorts results by price ascending
- [x] Write unit tests in `tests/test_checker.py` (10 tests, all passing):
  - [x] Normal deal within threshold is returned
  - [x] Price above threshold is excluded
  - [x] Suspiciously low price is excluded
  - [x] Duplicate date pairs deduplicated, lowest price kept
  - [x] Empty input returns empty list
  - [x] Price exactly at threshold is included
  - [x] Price $1 above threshold is excluded
  - [x] Results sorted price-ascending
  - [x] Price == min_price is included (boundary)
  - [x] Multiple date pairs deduped independently

**Acceptance Criteria**

- [x] `python -m pytest tests/test_checker.py` — 10/10 passing
- [x] Flight at exactly $150.00 is included
- [x] Flight at $151 is excluded
- [x] Flight at $9 is excluded when min_price is $10
- [x] Duplicate routes on same dates retain only cheaper option

---

### TICKET-004 — Resend Email Digest

- **Status:** [x]
- **Complexity:** Medium
- **Depends on:** TICKET-003

**Purpose**

Send a formatted HTML bi-weekly digest email grouped by route, sorted by price, with
working Google Flights booking links per deal.

**Tasks**

- [x] Sign up for Resend.com and obtain an API key
- [x] Implement `src/notifier.py`:
  - [x] `send_alert(deals_by_route, recipient_email, api_key, from_address, test_mode)`
  - [x] HTML email: blue header, summary banner, one table per route
  - [x] Columns: Depart | Return | Trip type | Price | Airline | Book (View button)
  - [x] Trip type auto-detected: "Weekend (Fri–Sun)" / "Long Weekend (Thu–Mon)" / "N-day trip"
  - [x] Subject: `✈ Flight Digest: SFO/SJC → LAS — cheapest from $XX`
  - [x] `[TEST]` prefix on subject when `test_mode=True`
  - [x] Guard clause: no-op when all deal lists are empty
  - [x] Descriptive `RuntimeError` on auth failure
- [x] Plain-text fallback body
- [x] Verified: HTML renders correctly in Gmail
- [x] Verified: "View" button links to correct Google Flights itinerary via `booking_token`

**Acceptance Criteria**

- [x] Email renders readable grouped table in Gmail
- [x] Subject uses lowest price across all routes
- [x] Each route section labeled and sorted price-ascending
- [x] Trip type visible per row (Fri-Sun vs Thu-Mon)
- [x] Function is no-op when all deal lists are empty
- [x] Invalid API key raises clear exception

---

### TICKET-005 — GitHub Actions Workflow

- **Status:** [x]
- **Complexity:** Medium
- **Depends on:** TICKET-001, TICKET-002, TICKET-004

**Purpose**

Run the script automatically on the 1st and 15th of each month on GitHub's servers,
with secrets injected at runtime.

**Tasks**

- [x] `.github/workflows/check_prices.yml` finalised:
  - [x] Cron: `0 13 1,15 * *` (1st and 15th at 1pm UTC)
  - [x] `workflow_dispatch` with `test_mode` boolean input
  - [x] Steps: checkout → Python 3.11 → pip install → `python main.py` (or `--test`)
  - [x] Secrets injected: `SERPAPI_KEY`, `RESEND_API_KEY`, `ALERT_EMAIL`
- [x] Secrets added to GitHub repo (Settings → Secrets → Actions)
- [x] Code pushed to GitHub (`main` branch)
- [ ] Validated via `workflow_dispatch` manual trigger on GitHub

**Acceptance Criteria**

- [x] Workflow YAML is syntactically correct
- [ ] Manual `workflow_dispatch` trigger runs successfully end-to-end on GitHub
- [ ] Workflow completes in under 3 minutes
- [ ] Cron fires on 1st and 15th (verify after first scheduled run)
- [x] Secrets are never printed to workflow logs
- [x] Non-zero Python exit code marks the run as failed

---

### TICKET-006 — Configuration System

- **Status:** [x]
- **Complexity:** Low
- **Depends on:** TICKET-001

**Purpose**

All user-tunable settings live in `config.yaml`. Changing routes, threshold, scan window,
or trip patterns requires no code changes.

**Tasks**

- [x] `config.example.yaml` finalised with schema:
  - routes, price_threshold, min_price_sanity, scan_months_ahead, trip_patterns
- [x] `config.yaml` created and committed (no secrets — safe to version)
- [x] Implement `src/config.py`:
  - [x] `load_config(path="config.yaml")` with full validation
  - [x] `Route` and `Config` dataclasses
  - [x] Raises `ValueError` with field name if required field missing
  - [x] Raises `FileNotFoundError` if config file not found
- [x] `main.py` wired: loads config → passes values to all modules

**Acceptance Criteria**

- [x] Adding a route to `config.yaml` causes it to be checked with no code changes
- [x] Reducing `scan_months_ahead` shrinks the date pairs scanned
- [x] Adding a new trip pattern generates the correct pairs
- [x] Missing required field raises `ValueError` naming the missing field
- [x] `config.example.yaml` committed with inline comments on every field

---

### TICKET-007 — Manual Test Mode

- **Status:** [x]
- **Complexity:** Low
- **Depends on:** TICKET-004, TICKET-005, TICKET-006

**Purpose**

Verify the full email pipeline end-to-end without real SerpAPI calls and without waiting
for the cron schedule.

**Tasks**

- [x] `--test` flag implemented in `main.py`:
  - [x] Skips SerpAPI entirely
  - [x] Injects fake deals for SFO→LAS (Fri-Sun, $99 Southwest) and SJC→LAS (Thu-Mon, $112 Frontier)
  - [x] Prints `[TEST MODE] Sending test digest to <email>`
  - [x] Sends real email via Resend with `[TEST]` subject prefix
- [x] `workflow_dispatch` exposes `test_mode` boolean input → passes `--test` to script
- [x] Verified: `python main.py --test` delivers correct email to `ALERT_EMAIL`

**Acceptance Criteria**

- [x] `python main.py --test` sends real email with fake deal data for both routes
- [x] Subject line includes `[TEST]`
- [x] No SerpAPI calls made in test mode
- [x] `workflow_dispatch` with `test_mode: true` passes `--test` to the script

---

### TICKET-008 — Documentation

- **Status:** [x]
- **Complexity:** Low
- **Depends on:** All other tickets

**Tasks**

- [x] Write `README.md` covering:
  - [x] **What it does** — 2-3 sentence description
  - [x] **Prerequisites** — Python 3.11+, GitHub account, SerpAPI account, Resend account
  - [x] **Account setup** — SerpAPI (key location, free tier limits) and Resend (sender verification, key)
  - [x] **Configuration** — copy `config.example.yaml` to `config.yaml`, edit routes/threshold/scan window
  - [x] **SerpAPI call budget** — explain 250/month limit and why `scan_months_ahead: 3` is the safe default
  - [x] **GitHub Secrets setup** — exact names: `SERPAPI_KEY`, `RESEND_API_KEY`, `ALERT_EMAIL`
  - [x] **Running locally** — `pip install -r requirements.txt` → `python main.py --test`
  - [x] **Verifying the workflow** — `workflow_dispatch`, where to check logs
  - [x] **Cron schedule** — explain `0 13 1,15 * *`, link to crontab.guru
  - [x] **Troubleshooting** — bad API key, Resend sender not verified, no flights found, exceeding SerpAPI limit

**Acceptance Criteria**

- [x] All three secret names in README exactly match the workflow YAML
- [x] README explains the bi-weekly schedule and call budget clearly
- [x] Troubleshooting covers 6 distinct failure scenarios
- [x] A new reader can go from zero to running in under 30 minutes

---

## Suggested Build Order

```
TICKET-001  (setup) ✅
     │
     ├──► TICKET-006  (config) ✅
     │
     ├──► TICKET-002  (SerpAPI integration) ✅
     │         │
     │         └──► TICKET-003  (price logic) ✅
     │                   │
     │                   └──► TICKET-004  (email digest) ✅
     │                             │
     └──────────────────────────── └──► TICKET-005  (GitHub Actions) ✅
                                             │
                                        TICKET-007  (test mode) ✅
                                             │
                                        TICKET-008  (docs) ✅
```

---

## Open Questions

- [x] ~~Travelpayouts vs SerpAPI~~ — **Resolved: SerpAPI.**
- [x] ~~Daily vs weekly vs bi-weekly~~ — **Resolved: bi-weekly (1st and 15th), SFO/SJC→LAS only.**
- [x] ~~Which trip patterns~~ — **Resolved: Fri→Sun (2 nights) and Thu→Mon (4 nights, long weekend).**
- [x] ~~How far ahead to scan~~ — **Resolved: 3-month rolling window anchored to today's date.**
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

| Parameter         | Value / Example    | Notes                                         |
|-------------------|--------------------|-----------------------------------------------|
| `engine`          | `google_flights`   | Required                                      |
| `departure_id`    | `SFO`              | IATA code                                     |
| `arrival_id`      | `LAS`              | IATA code                                     |
| `outbound_date`   | `2026-04-10`       | YYYY-MM-DD (Thursday or Friday)               |
| `return_date`     | `2026-04-13`       | YYYY-MM-DD (Monday or Sunday)                 |
| `type`            | `1`                | 1 = round trip, 2 = one way                   |
| `currency`        | `USD`              |                                               |
| `departure_token` | `<from call 1>`    | Only on Call 2; triggers combined pricing     |
| `api_key`         | `SERPAPI_KEY`      | From env var                                  |

**Response fields used:**

| Field            | Source  | Used for                                       |
|------------------|---------|------------------------------------------------|
| `best_flights`   | Call 1  | Cheapest outbound, extract `departure_token`   |
| `other_flights`  | Call 1  | Fallback outbound options                      |
| `best_flights`   | Call 2  | Combined round-trip `price` + `booking_token`  |
| `booking_token`  | Call 2  | Constructs Google Flights deep-link in email   |

### Resend

- **Docs:** https://resend.com/docs
- **Python package:** `resend` (`pip install resend`)
- **Free tier:** 3,000 emails/month

---

*Last updated: 2026-03-06*
