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
│   (TRAVELPAYOUTS_TOKEN, RESEND_API_KEY, ALERT_EMAIL)            │
│         │                                                       │
│         ▼                                                       │
│   python main.py                                                │
└────────────────────┬────────────────────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          │                     │
          ▼                     ▼
┌──────────────────┐   ┌─────────────────────┐
│ Travelpayouts    │   │   config.yaml        │
│ Prices API       │   │                      │
│                  │   │  routes:             │
│  GET /v1/prices  │   │    - origin: SFO     │
│  /cheap          │   │      dest: LAS       │
│                  │   │  threshold: 150      │
│  returns cached  │   │  departure_months:   │
│  lowest fares    │   │    - 2026-04         │
│  by date         │   │    - 2026-05         │
└────────┬─────────┘   └─────────────────────┘
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

| Component          | Tool / Service           | Notes                              |
|--------------------|--------------------------|------------------------------------|
| Language           | Python 3.11+             |                                    |
| Flight data        | Travelpayouts Prices API | Free, returns cached lowest fares  |
| Email delivery     | Resend.com               | Free tier: 3,000 emails/month      |
| Scheduling / CI    | GitHub Actions           | Free for public repos              |
| Secrets management | GitHub Secrets           | Injected as env vars at runtime    |
| Configuration      | config.yaml              | Versioned in repo, no code changes |

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

- **Status:** [ ]
- **Complexity:** Low
- **Depends on:** Nothing

**Purpose**

Establish the repository structure, dependency management, and guardrails so all subsequent
tickets have a clean foundation to build on.

**Tasks**

- [ ] Create repo directory layout:
  ```
  flight-tracker/
  ├── .github/
  │   └── workflows/
  │       └── check_prices.yml
  ├── src/
  │   ├── __init__.py
  │   ├── api.py          # Travelpayouts client
  │   ├── checker.py      # price comparison logic
  │   ├── notifier.py     # Resend email client
  │   └── config.py       # config loader
  ├── tests/
  │   └── test_checker.py
  ├── config.yaml         # user-editable settings
  ├── config.example.yaml # committed template with comments
  ├── requirements.txt
  ├── .gitignore
  ├── README.md
  └── main.py             # entry point
  ```
- [ ] Add `requirements.txt` with pinned versions: `requests`, `pyyaml`, `resend`, `python-dotenv`
- [ ] Add `.gitignore` covering: `__pycache__/`, `*.pyc`, `.env`, `config.yaml` (keep only `config.example.yaml` in source control if config contains any personal data — or keep it committed since it contains no secrets)
- [ ] Add `config.example.yaml` with all fields documented inline
- [ ] Verify `python -m pip install -r requirements.txt` runs without errors

**Acceptance Criteria**

- [ ] Running `pip install -r requirements.txt` in a clean virtual environment succeeds
- [ ] `python main.py` runs without import errors (even if it does nothing yet)
- [ ] No secrets, `.env` files, or personal data are committed to the repo
- [ ] Directory structure matches the layout above

---

### TICKET-002 — Travelpayouts API Integration

- **Status:** [ ]
- **Complexity:** Medium
- **Depends on:** TICKET-001

**Purpose**

Build the module that fetches cached lowest flight prices from the Travelpayouts Prices API
for a given origin, destination, and set of target months. This is the data layer — all
other logic depends on it returning clean, structured results.

**Tasks**

- [ ] Sign up for a Travelpayouts account and obtain an API token
- [ ] Read the [Prices API docs](https://support.travelpayouts.com/hc/en-us/articles/203956173) and confirm which endpoint returns cheapest one-way and round-trip prices by month (`/v2/prices/month-matrix` or `/v1/prices/cheap`)
- [ ] Implement `src/api.py`:
  - `get_cheapest_round_trips(origin, destination, months, token)` function
  - Handles HTTP errors and non-200 responses with descriptive exceptions
  - Returns a list of dicts: `[{"depart_date": "2026-04-10", "return_date": "2026-04-14", "price": 124, "airline": "WN", "link": "..."}]`
  - Respects API rate limits (add a small sleep between requests if fetching multiple months)
- [ ] Add a `__main__` block to `src/api.py` for quick manual testing: `python -m src.api`

**Acceptance Criteria**

- [ ] `get_cheapest_round_trips("SFO", "LAS", ["2026-04"], token)` returns a non-empty list when deals exist for that month
- [ ] Function raises a clear exception (not a silent failure) when the API token is invalid
- [ ] Function returns an empty list (not an error) when no flights are found for a route
- [ ] Manual test (`python -m src.api`) prints results to stdout without crashing

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
  - Each deal row shows: departure date, return date, price, airline code, booking link
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
    - `TRAVELPAYOUTS_TOKEN` → from GitHub Secret
    - `RESEND_API_KEY` → from GitHub Secret
    - `ALERT_EMAIL` → from GitHub Secret
- [ ] Add secrets to the GitHub repo (Settings → Secrets and variables → Actions)
- [ ] Test via `workflow_dispatch` before relying on the cron schedule

**Acceptance Criteria**

- [ ] Workflow file passes YAML lint (`yamllint` or GitHub's built-in validator)
- [ ] Manual trigger (`workflow_dispatch`) runs successfully end-to-end in GitHub Actions
- [ ] Workflow completes in under 2 minutes on a normal run
- [ ] Cron trigger fires on schedule (verify via Actions tab after 24 hours)
- [ ] Secrets are never printed to workflow logs (no `echo $RESEND_API_KEY` anywhere)
- [ ] If the Python script exits with a non-zero code, the workflow run is marked as failed

---

### TICKET-006 — Configuration System

- **Status:** [ ]
- **Complexity:** Low
- **Depends on:** TICKET-001

**Purpose**

Make the tracker useful beyond the initial SFO → LAS use case without requiring code
changes. All user-tunable settings live in `config.yaml` and are validated at startup.

**Tasks**

- [ ] Define `config.example.yaml` schema:
  ```yaml
  routes:
    - origin: SFO
      destination: LAS
      # Add more routes as needed
    - origin: SFO
      destination: JFK

  price_threshold: 150       # Max round-trip price in USD to trigger alert
  min_price_sanity: 10       # Ignore prices below this (likely bad data)

  departure_months:
    - "2026-04"
    - "2026-05"

  trip_length_min_days: 2    # Minimum trip length filter (optional, 0 = no filter)
  trip_length_max_days: 7    # Maximum trip length filter (optional, 0 = no filter)
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
  - Inject a hardcoded fake deal: `{"depart_date": "2026-04-10", "return_date": "2026-04-14", "price": 99, "airline": "WN", "link": "https://example.com"}`
  - Run the full notifier pipeline with the fake deal
  - Print `[TEST MODE] Sending test alert to <email>` to stdout
- [ ] Document the flag in the README
- [ ] Add `--test` support to the GitHub Actions workflow as an optional input on `workflow_dispatch`

**Acceptance Criteria**

- [ ] `python main.py --test` sends a real email to `ALERT_EMAIL` with the fake deal data
- [ ] Test mode email subject clearly indicates it is a test (e.g., `[TEST] Flight Alert: ...`)
- [ ] Running `python main.py --test` does not make any calls to the Travelpayouts API
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
  - [ ] **Prerequisites** — Python 3.11+, a GitHub account, a Travelpayouts account, a Resend account
  - [ ] **Account setup** — step-by-step for Travelpayouts (where to find the API token) and Resend (how to verify a sender, where to find the API key)
  - [ ] **Configuration** — how to copy `config.example.yaml` to `config.yaml` and edit routes/threshold/months
  - [ ] **GitHub Secrets setup** — exact secret names to create (`TRAVELPAYOUTS_TOKEN`, `RESEND_API_KEY`, `ALERT_EMAIL`) and where to add them in the GitHub UI
  - [ ] **Running locally** — `pip install -r requirements.txt` and `python main.py --test`
  - [ ] **Verifying the workflow** — how to trigger manually via `workflow_dispatch` and where to check logs
  - [ ] **Customizing the cron schedule** — link to crontab.guru, explain the current schedule
  - [ ] **Troubleshooting** — common failure modes: bad API token, no sender domain verified in Resend, no flights found for route

**Acceptance Criteria**

- [ ] A person unfamiliar with the codebase can follow the README and have the tracker running without asking any clarifying questions
- [ ] All three secret names in the README exactly match the names used in the workflow YAML
- [ ] README includes a note that `config.yaml` should not be committed if it contains personal info (email addresses, etc.)
- [ ] Troubleshooting section covers at least 3 distinct failure scenarios

---

## Suggested Build Order

```
TICKET-001  (setup)
     │
     ├──► TICKET-006  (config)
     │
     ├──► TICKET-002  (API integration)
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

Build TICKET-001 and TICKET-006 first since they have no dependencies and unblock everything
else. TICKET-002, TICKET-003, and TICKET-004 form the core pipeline and should be built and
tested locally in sequence. TICKET-005 comes after the pipeline is proven to work locally.
TICKET-007 and TICKET-008 are final polish.

---

## Open Questions

- [ ] Does Travelpayouts return round-trip prices directly, or does round-trip need to be
      calculated as outbound + return legs? (Check API docs before starting TICKET-002)
- [ ] Should multiple matching deals be listed in a single email, or one email per deal?
      (Current plan: one email per run, all deals listed in a table)
- [ ] What should happen if the Travelpayouts API returns no data for a month?
      (Current plan: log a warning, continue to next route/month, do not error)
- [ ] Is there a need to track historical prices over time, or is stateless (check and alert) sufficient?
      (Current plan: stateless — no database, no persistence between runs)

---

*Last updated: 2026-03-05*
