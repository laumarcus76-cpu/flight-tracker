# Flight Price Tracker — Project Plan

## Overview

A lightweight personal tool that monitors specific flight routes and sends an email alert
when round-trip prices drop below a configurable threshold (default: $150). It runs entirely
in the cloud on a cron schedule using GitHub Actions — no home server or always-on machine
required.

**Core value:** Wake up to an email saying "SFO → LAS round trip: $118" instead of
manually checking Google Flights every week.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        GitHub Actions                           │
│                                                                 │
│   cron schedule (e.g., daily at 8am UTC)                        │
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
┌──────────────────┐   ┌─────────────────────┐
│ SerpAPI          │   │   config.yaml        │
│ Google Flights   │   │                      │
│                  │   │  routes:             │
│  Step 1:         │   │    - origin: SFO     │
│  GET outbound    │   │      dest: LAS       │
│  flights →       │   │    - origin: SJC     │
│  departure_token │   │      dest: LAS       │
│                  │   │  threshold: 150      │
│  Step 2:         │   │  departure_months:   │
│  GET return      │   │    - 2026-04         │
│  flights using   │   │    - 2026-05         │
│  departure_token │   └─────────────────────┘
│  → round-trip    │
│  combined price  │
│                  │
│  Covers all LCCs │
│  (SW, Frontier,  │
│  Spirit,         │
│  Allegiant)      │
└────────┬─────────┘
         │
         ▼
  price comparison logic
  (filter < threshold,
   reject suspiciously low,
   deduplicate)
         │
         ├─── no deals found ──► exit 0 (no email sent)
         │
         ▼
  format alert payload
  (route, price, dates,
   deep-link to booking)
         │
         ▼
┌─────────────────────┐
│   Resend.com API    │
│                     │
│  POST /emails       │
│  HTML email with    │
│  flight details     │
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

### SerpAPI Google Flights — Two-Call Flow

Fetching a round-trip price requires two sequential API calls per (origin, destination, date-pair):

1. **Call 1 — Outbound search:**
   ```
   GET https://serpapi.com/search
   ?engine=google_flights
   &departure_id=SFO
   &arrival_id=LAS
   &outbound_date=2026-04-10
   &return_date=2026-04-14
   &type=1              ← round trip
   &currency=USD
   &api_key=SERPAPI_KEY
   ```
   Returns outbound flight options. Each option includes a `departure_token`.

2. **Call 2 — Return + combined price:**
   ```
   GET https://serpapi.com/search
   ?engine=google_flights
   &departure_id=SFO
   &arrival_id=LAS
   &outbound_date=2026-04-10
   &return_date=2026-04-14
   &type=1
   &departure_token=<token_from_call_1>
   &currency=USD
   &api_key=SERPAPI_KEY
   ```
   Returns return flight options with the **combined round-trip price** for each pairing.

**Budget:** At 1 check/day with 2 origins (SFO + SJC) × 2 calls = ~4 calls/day × 30 = ~120 calls/month.
Free tier allows 250/month — comfortably within budget. Add date-range scanning and budget accordingly.

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
- [x] Add `requirements.txt` with pinned versions: `google-search-results`, `pyyaml`, `resend`, `python-dotenv`
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

- **Status:** [ ]
- **Complexity:** Medium
- **Depends on:** TICKET-001

**Purpose**

Build the module that fetches real-time round-trip flight prices from Google Flights via
SerpAPI for a given origin, destination, and set of target date pairs. SerpAPI returns
live, bookable prices aggregated from all carriers including low-cost carriers (Southwest,
Frontier, Spirit, Allegiant) — the carriers most likely to have sub-$150 SFO/SJC→LAS fares.

**SerpAPI account setup:**
- Sign up at https://serpapi.com (free, instant, no approval)
- Free tier: 250 searches/month
- API key available immediately in the dashboard

**Tasks**

- [ ] Sign up for SerpAPI and obtain an API key
- [ ] Read the [SerpAPI Google Flights docs](https://serpapi.com/google-flights-api) to confirm
      the two-call round-trip flow (outbound → departure_token → return + combined price)
- [ ] Implement `src/api.py`:
  - `get_cheapest_round_trips(origin, destination, date_pairs, api_key)` function
    - `date_pairs`: list of `(depart_date, return_date)` tuples as `"YYYY-MM-DD"` strings
    - For each date pair, makes 2 sequential API calls (outbound, then return with token)
    - Extracts the cheapest combined round-trip price per date pair from Call 2 results
    - Adds a small sleep (0.5s) between date pairs to respect rate limits
    - Handles HTTP errors and non-200 responses with descriptive exceptions
    - Returns a list of dicts:
      ```python
      [
        {
          "depart_date": "2026-04-10",
          "return_date": "2026-04-14",
          "price": 124,
          "airline": "Southwest",
          "link": "https://www.google.com/flights/..."
        }
      ]
      ```
  - `generate_date_pairs(months, min_days, max_days)` helper
    - Given a list of `"YYYY-MM"` months and trip length bounds, generates all
      (Friday, Sunday) or configurable weekday pairs within each month
- [ ] Add a `__main__` block to `src/api.py` for quick manual testing: `python -m src.api`

**Acceptance Criteria**

- [ ] `get_cheapest_round_trips("SFO", "LAS", [("2026-04-10", "2026-04-14")], key)` returns
      a non-empty list when Google Flights has results for that route/date
- [ ] Function raises a clear exception (not a silent failure) when the API key is invalid
- [ ] Function returns an empty list (not an error) when no flights are found for a date pair
- [ ] Manual test (`python -m src.api`) prints results to stdout without crashing
- [ ] Both SFO and SJC origins work as valid `origin` inputs

---

### TICKET-003 — Price Comparison Logic

- **Status:** [ ]
- **Complexity:** Medium
- **Depends on:** TICKET-002

**Purpose**

Filter the raw API results down to actionable deals. This layer applies the price threshold,
rejects data anomalies (e.g., $1 fares that are API errors), and deduplicates results so
the email is clean and readable.

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

**Acceptance Criteria**

- [ ] `python -m pytest tests/test_checker.py` passes with all tests green
- [ ] A flight at exactly the threshold price ($150.00) is included (boundary condition)
- [ ] A flight at $151 is excluded
- [ ] A flight at $9 is excluded when min_price is $10
- [ ] Duplicate routes on same dates retain only the cheaper option

---

### TICKET-004 — Resend Email Integration

- **Status:** [ ]
- **Complexity:** Medium
- **Depends on:** TICKET-003

**Purpose**

Send a formatted HTML email when deals are found. The email should be immediately actionable:
include the route, price, travel dates, and a link to book. One email per run (batched),
not one email per deal.

**Tasks**

- [ ] Sign up for Resend.com and obtain an API key
- [ ] Verify a sender domain or use the Resend sandbox address for testing
- [ ] Implement `src/notifier.py`:
  - `send_alert(deals, route, recipient_email, api_key)` function
  - Builds an HTML email body listing all deals in a readable table
  - Subject line: `Flight Alert: SFO → LAS from $XX`  (uses the lowest price found)
  - Each deal row shows: departure date, return date, price, airline, booking link
  - Does not send if `deals` is empty (guard clause)
- [ ] Add a plain-text fallback body for email clients that don't render HTML

**Acceptance Criteria**

- [ ] Calling `send_alert` with one deal delivers an email to the recipient address
- [ ] Subject line correctly reflects the lowest price in the deals list
- [ ] Email renders a readable table in Gmail and Apple Mail
- [ ] Function is a no-op (returns early, no API call made) when `deals` is empty
- [ ] Invalid API key raises an exception with a clear message, not a silent failure

---

### TICKET-005 — GitHub Actions Workflow

- **Status:** [ ]
- **Complexity:** Medium
- **Depends on:** TICKET-001, TICKET-002, TICKET-004

**Purpose**

Wire everything together so the script runs automatically in the cloud on a schedule.
GitHub Actions provides free compute, secret injection, and cron scheduling without
any infrastructure to maintain.

**Tasks**

- [ ] Create `.github/workflows/check_prices.yml`:
  - Trigger: `schedule` (cron) + `workflow_dispatch` (manual trigger from GitHub UI)
  - Cron: `0 13 * * *` (daily at 1pm UTC / 5am or 6am Pacific depending on DST)
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

- [ ] Workflow file passes YAML lint (`yamllint` or GitHub's built-in validator)
- [ ] Manual trigger (`workflow_dispatch`) runs successfully end-to-end in GitHub Actions
- [ ] Workflow completes in under 2 minutes on a normal run
- [ ] Cron trigger fires on schedule (verify via Actions tab after 24 hours)
- [ ] Secrets are never printed to workflow logs (no `echo $SERPAPI_KEY` anywhere)
- [ ] If the Python script exits with a non-zero code, the workflow run is marked as failed

---

### TICKET-006 — Configuration System

- **Status:** [ ]
- **Complexity:** Low
- **Depends on:** TICKET-001

**Purpose**

Make the tracker useful beyond the initial SFO/SJC → LAS use case without requiring code
changes. All user-tunable settings live in `config.yaml` and are validated at startup.

**Tasks**

- [ ] Define `config.example.yaml` schema:
  ```yaml
  routes:
    - origin: SFO          # IATA code
      destination: LAS
    - origin: SJC          # Check both Bay Area airports
      destination: LAS

  price_threshold: 150       # Max round-trip price in USD to trigger alert
  min_price_sanity: 10       # Ignore prices below this (likely bad data)

  departure_months:
    - "2026-04"
    - "2026-05"

  trip_length_min_days: 2    # Minimum trip length filter (0 = no filter)
  trip_length_max_days: 7    # Maximum trip length filter (0 = no filter)
  ```
- [ ] Implement `src/config.py`:
  - `load_config(path="config.yaml")` function
  - Validates required fields are present; raises `ValueError` with a clear message if not
  - Returns a typed dict or dataclass
- [ ] Update `main.py` to load config first and pass values to all modules

**Acceptance Criteria**

- [ ] Adding a second route to `config.yaml` causes both routes to be checked with no code changes
- [ ] Changing `price_threshold` to 100 correctly filters results without touching any `.py` file
- [ ] Missing required field (e.g., no `routes`) raises a `ValueError` with a message explaining what is missing
- [ ] `config.example.yaml` is committed and contains inline comments explaining every field

---

### TICKET-007 — Manual Test Mode

- **Status:** [ ]
- **Complexity:** Low
- **Depends on:** TICKET-004, TICKET-005, TICKET-006

**Purpose**

Provide a way to trigger a test alert email without waiting for the cron job and without
needing actual cheap flights to exist. Essential for verifying the full email pipeline
works before deployment.

**Tasks**

- [ ] Add a `--test` flag to `main.py`:
  - When passed, skip the API call entirely
  - Inject a hardcoded fake deal: `{"depart_date": "2026-04-10", "return_date": "2026-04-14", "price": 99, "airline": "Southwest", "link": "https://example.com"}`
  - Run the full notifier pipeline with the fake deal
  - Print `[TEST MODE] Sending test alert to <email>` to stdout
- [ ] Document the flag in the README
- [ ] Add `--test` support to the GitHub Actions workflow as an optional input on `workflow_dispatch`

**Acceptance Criteria**

- [ ] `python main.py --test` sends a real email to `ALERT_EMAIL` with the fake deal data
- [ ] Test mode email subject clearly indicates it is a test (e.g., `[TEST] Flight Alert: ...`)
- [ ] Running `python main.py --test` does not make any calls to the SerpAPI
- [ ] The GitHub Actions `workflow_dispatch` trigger exposes a `test_mode` boolean input that passes `--test` to the script when set to `true`

---

### TICKET-008 — Documentation

- **Status:** [ ]
- **Complexity:** Low
- **Depends on:** All other tickets

**Purpose**

Write a README that allows someone (including future-you) to go from zero to a running
flight tracker in under 30 minutes. Cover account setup, secret configuration, and how
to verify the system is working.

**Tasks**

- [ ] Write `README.md` covering:
  - [ ] **What it does** — 2-3 sentence description
  - [ ] **Prerequisites** — Python 3.11+, a GitHub account, a SerpAPI account, a Resend account
  - [ ] **Account setup** — step-by-step for SerpAPI (where to find the API key, free tier limits) and Resend (how to verify a sender, where to find the API key)
  - [ ] **Configuration** — how to copy `config.example.yaml` to `config.yaml` and edit routes/threshold/months
  - [ ] **GitHub Secrets setup** — exact secret names (`SERPAPI_KEY`, `RESEND_API_KEY`, `ALERT_EMAIL`) and where to add them in the GitHub UI
  - [ ] **Running locally** — `pip install -r requirements.txt` and `python main.py --test`
  - [ ] **Verifying the workflow** — how to trigger manually via `workflow_dispatch` and where to check logs
  - [ ] **Customizing the cron schedule** — link to crontab.guru, explain the current schedule
  - [ ] **Troubleshooting** — common failure modes: bad API key, no sender domain verified in Resend, no flights found for route, exceeding SerpAPI free tier (250/month)
  - [ ] **SerpAPI free tier note** — 250 searches/month; explain call budget (2 origins × 2 calls × 30 days = ~120/month)

**Acceptance Criteria**

- [ ] A person unfamiliar with the codebase can follow the README and have the tracker running without asking any clarifying questions
- [ ] All three secret names in the README exactly match the names used in the workflow YAML
- [ ] README includes a note that `config.yaml` should not be committed if it contains personal info (email addresses, etc.)
- [ ] Troubleshooting section covers at least 3 distinct failure scenarios

---

## Suggested Build Order

```
TICKET-001  (setup) ✅
     │
     ├──► TICKET-006  (config)
     │
     ├──► TICKET-002  (SerpAPI integration)
     │         │
     │         └──► TICKET-003  (price logic)
     │                   │
     │                   └──► TICKET-004  (email)
     │                             │
     └──────────────────────────── └──► TICKET-005  (GitHub Actions)
                                             │
                                        TICKET-007  (test mode)
                                             │
                                        TICKET-008  (docs)
```

---

## Open Questions

- [x] ~~Does Travelpayouts return round-trip prices directly?~~ — **Resolved: switched to SerpAPI.**
      SerpAPI requires two calls (outbound → token → return + combined price).
- [ ] Should multiple matching deals be listed in a single email, or one email per deal?
      (Current plan: one email per run, all deals listed in a table)
- [ ] What should happen if SerpAPI returns no data for a date pair?
      (Current plan: log a warning, continue to next date pair / route, do not error)
- [ ] Is there a need to track historical prices over time, or is stateless (check and alert) sufficient?
      (Current plan: stateless — no database, no persistence between runs)
- [ ] Date pair strategy: check fixed (depart_date, return_date) pairs, or scan all
      (Friday, Sunday) combinations within each departure month?
      (Recommended: scan all Fri→Sun pairs within each month for broader coverage)

---

## API Reference

### SerpAPI Google Flights

- **Docs:** https://serpapi.com/google-flights-api
- **Base URL:** `https://serpapi.com/search`
- **Auth:** `api_key` query parameter
- **Free tier:** 250 searches/month, instant signup
- **Python package:** `google-search-results` (`pip install google-search-results`)

**Key parameters:**

| Parameter        | Value / Example        | Notes                                      |
|------------------|------------------------|--------------------------------------------|
| `engine`         | `google_flights`       | Required                                   |
| `departure_id`   | `SFO`                  | IATA code                                  |
| `arrival_id`     | `LAS`                  | IATA code                                  |
| `outbound_date`  | `2026-04-10`           | YYYY-MM-DD                                 |
| `return_date`    | `2026-04-14`           | YYYY-MM-DD                                 |
| `type`           | `1`                    | 1 = round trip, 2 = one way                |
| `currency`       | `USD`                  |                                            |
| `departure_token`| `<from call 1>`        | Only on Call 2; triggers combined pricing  |
| `api_key`        | `SERPAPI_KEY`          | From env var                               |

### Resend

- **Docs:** https://resend.com/docs
- **Python package:** `resend` (`pip install resend`)
- **Free tier:** 3,000 emails/month

---

*Last updated: 2026-03-05*
