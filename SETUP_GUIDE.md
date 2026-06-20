# Finance First Services — Mutual Fund Tracker
## Complete Setup & Usage Guide

---

## What This Does

Every weekday, the script:
1. Opens Finance First Services in a hidden browser
2. Logs in with your credentials
3. Reads **Invested** (e.g. `27,57,184.07`) and **Current Value** (e.g. `28,97,452.78`)
4. Rounds both to nearest integer → `27,57,184` and `28,97,453`
5. Finds today's date row in your Google Sheet (current month worksheet)
6. Writes the two values into **Amount Invested** (col B) and **Current Market Value** (col C)
7. Columns D (Unrealised P/L) and E (Profit/Loss %) auto-calculate via formulas

Your sheet layout is preserved exactly:
- Columns: Date | Amount Invested | Current Market Value | Unrealised P/L | Profit/Loss %
- Odd rows → light green `#E2EFDA`
- Even rows → light pink `#FCE4D6`
- Summary row → lavender `#CFE2F3` with "Month End Overall Profit/Loss %"
- Line chart to the right: "Monthly Growth %" — red line, data labels, cream background

---

## File Structure

```
fund_tracker/
├── tracker.py                ← Main script — runs daily
├── step1_find_selectors.py   ← Run ONCE to find HTML element IDs on dashboard
├── step2_test_sheets.py      ← Run ONCE to verify Google Sheets connection
├── .env                      ← YOUR SECRETS (you create this from .env.template)
├── .env.template             ← Template — safe to share/backup
├── .gitignore
└── logs/
    ├── tracker.log           ← Auto-created, every run appended here
    └── dashboard_screenshot.png  ← Created on errors for debugging
```

---

## PART 1 — Install Python

Download Python 3.11+ from **https://python.org/downloads**

> **Windows:** During install, tick ✅ **"Add Python to PATH"**

Confirm in terminal:
```bash
python --version
# → Python 3.11.x or higher
```

---

## PART 2 — Set Up the Project

### 2.1 — Place files in a folder

Create a folder anywhere, e.g.:
- Windows: `C:\Users\YourName\fund_tracker\`
- Mac: `/Users/yourname/fund_tracker/`

Put all 5 files inside it: `tracker.py`, `step1_find_selectors.py`,
`step2_test_sheets.py`, `.env.template`, `.gitignore`

### 2.2 — Create a virtual environment

Open a terminal/command prompt **inside your fund_tracker folder**:

```bash
python -m venv venv
```

Activate it:
```bash
# Windows:
venv\Scripts\activate

# Mac / Linux:
source venv/bin/activate
```

Your prompt now shows `(venv)` — keep this active for all steps below.

### 2.3 — Install packages

```bash
pip install playwright python-dotenv gspread google-auth
playwright install chromium
```

### 2.4 — Create your .env file

Copy the template:
```bash
# Windows:
copy .env.template .env

# Mac / Linux:
cp .env.template .env
```

Open `.env` in any text editor and fill in:
```env
INVESTMENT_USERNAME=your_actual_username
INVESTMENT_PASSWORD=your_actual_password
GOOGLE_SHEETS_ID=        ← fill in Part 3
SERVICE_ACCOUNT_FILE=    ← fill in Part 3
```

---

## PART 3 — Google Sheets API Setup

This gives the script permission to write to your Sheet without
ever using your personal Google login.

### 3.1 — Create a Google Cloud Project

1. Go to **https://console.cloud.google.com**
2. Top-left dropdown → **New Project**
3. Name: `FundTracker` → **Create**
4. Make sure `FundTracker` is selected in the top-left dropdown

### 3.2 — Enable APIs

1. Left menu → **APIs & Services → Library**
2. Search **"Google Sheets API"** → **Enable**
3. Back to Library → search **"Google Drive API"** → **Enable**

### 3.3 — Create a Service Account

1. Left menu → **APIs & Services → Credentials**
2. Click **+ Create Credentials → Service Account**
3. Name: `fund-tracker-bot` → **Create and Continue** → **Done**

### 3.4 — Download the JSON key

1. On the Credentials page, click your `fund-tracker-bot` email link
2. Go to the **Keys** tab
3. **Add Key → Create New Key → JSON → Create**
4. A `.json` file downloads automatically
5. Move it somewhere permanent and safe:
   - Windows: `C:\Users\YourName\credentials\fund_tracker_key.json`
   - Mac: `/Users/yourname/credentials/fund_tracker_key.json`

> ⚠️ Do NOT put this file in Google Drive, Dropbox, or OneDrive

### 3.5 — Share your Google Sheet with the service account

1. Go to **https://console.cloud.google.com → Credentials**
2. Copy the service account email — it looks like:
   `fund-tracker-bot@fundtracker-xxxxxx.iam.gserviceaccount.com`
3. Open your Google Sheet → click **Share** (top right)
4. Paste the service account email → set role to **Editor** → **Send**

### 3.6 — Find your Sheet ID

From your Sheet's browser URL:
```
https://docs.google.com/spreadsheets/d/ ← THIS IS YOUR SHEET ID → /edit
```
Copy the long string between `/d/` and `/edit`.

### 3.7 — Update .env

```env
GOOGLE_SHEETS_ID=the_long_id_you_just_copied
SERVICE_ACCOUNT_FILE=C:\Users\YourName\credentials\fund_tracker_key.json
```

---

## PART 4 — Discover Login Selectors (run once)

The script auto-detects most login forms, but if it fails,
run this to find the exact element IDs for the Finance First Services portal.

```bash
python step1_find_selectors.py
```

This opens a **visible** browser window, logs in, then prints:
- All input fields on the login page
- All elements on the dashboard containing large numbers (your investment amounts)

Look in section **[6]** for rows matching your Invested and Current Value amounts.
Note the `id=` values and if needed add them to `.env`:
```env
SELECTOR_INVESTED=#the_id_here
SELECTOR_CURRENT_VALUE=#the_other_id
```

---

## PART 5 — Test Google Sheets (run once)

```bash
python step2_test_sheets.py
```

This creates a test worksheet with sample data and the line chart.
Open your Google Sheet and verify everything looks correct before running
the real tracker.

---

## PART 6 — Test the Main Tracker

### Dry run (no sheet write):
```bash
python tracker.py --dry-run
```

Expected output:
```
2026-06-20 18:30:01  INFO  Finance First Services — Tracker starting
2026-06-20 18:30:04  INFO  Launching browser → Finance First Services dashboard...
2026-06-20 18:30:07  INFO  Username filled using selector: input[placeholder='Username']
2026-06-20 18:30:09  INFO  Password filled using selector: input[type='password']
2026-06-20 18:30:09  INFO  Login button clicked using selector: button:has-text('Login')
2026-06-20 18:30:13  INFO  Dashboard URL: https://portfolio.financefirstservices.com/...
2026-06-20 18:30:14  INFO  Scraped  →  Invested: ₹27,57,184  |  Current Value: ₹28,97,453
2026-06-20 18:30:14  INFO  DRY RUN — values scraped but NOT written to sheet:
2026-06-20 18:30:14  INFO    Invested      = ₹27,57,184
2026-06-20 18:30:14  INFO    Current Value = ₹28,97,453
2026-06-20 18:30:14  INFO    P/L           = ₹1,40,269
```

### Real run (writes to sheet):
```bash
python tracker.py
```

---

## PART 7 — Troubleshooting

| Problem | What to do |
|---|---|
| `Could not find username field` | Run `step1_find_selectors.py` and set `SELECTOR_*` in `.env` |
| `Value extraction failed — see logs/debug_screenshot.png` | Open the screenshot. Run `step1_find_selectors.py` to get selectors |
| `Date '20 Jun' not found in column A` | Check the sheet — may be a market holiday or the date format differs |
| `SpreadsheetNotFound` | Confirm `GOOGLE_SHEETS_ID` in `.env` and that you shared the Sheet |
| `Permission denied on sheet` | Re-share the Sheet with your service account email as **Editor** |
| `ModuleNotFoundError` | Make sure `(venv)` is active: `venv\Scripts\activate` |
| Script ran but sheet has wrong values | Check `logs/tracker.log` — values logged before sheet write |

---

## PART 8 — Schedule Daily Automatic Runs

Indian markets close at **3:30 PM IST**. Run the script at **4:00 PM** or later.

### Windows — Task Scheduler

1. Press `Win + S` → search **Task Scheduler** → open it
2. Right panel → **Create Basic Task**
3. **Name:** `Fund Tracker`
4. **Trigger:** Daily
5. **Start time:** `4:00 PM`  (or your preferred time after market close)
6. **Action:** Start a Program
7. **Program/script:**
   ```
   C:\Users\YourName\fund_tracker\venv\Scripts\python.exe
   ```
8. **Add arguments:**
   ```
   tracker.py
   ```
9. **Start in (working directory):**
   ```
   C:\Users\YourName\fund_tracker\
   ```
10. Click **Finish**
11. Right-click the task → **Properties → Conditions** tab →
    uncheck **"Start only if on AC power"** (if using a laptop)

> The script automatically skips weekends — no extra configuration needed.

### Mac — Launchd

Create the file `~/Library/LaunchAgents/com.yourname.fundtracker.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.yourname.fundtracker</string>

  <key>ProgramArguments</key>
  <array>
    <string>/Users/yourname/fund_tracker/venv/bin/python</string>
    <string>/Users/yourname/fund_tracker/tracker.py</string>
  </array>

  <key>WorkingDirectory</key>
  <string>/Users/yourname/fund_tracker</string>

  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>16</integer>
    <key>Minute</key><integer>0</integer>
  </dict>

  <key>StandardOutPath</key>
  <string>/Users/yourname/fund_tracker/logs/launchd.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/yourname/fund_tracker/logs/launchd_error.log</string>
</dict>
</plist>
```

Load it:
```bash
launchctl load ~/Library/LaunchAgents/com.yourname.fundtracker.plist
```

---

## PART 9 — How Month-End Works Automatically

On the **first weekday of a new month**, the script detects that
the worksheet for that month doesn't exist yet and automatically:

1. Creates a new worksheet named e.g. `July 2026`
2. Adds the header row with all 5 column names
3. Pre-fills **all weekday dates** (Mon–Fri) for that month in column A
4. Sets up `=C-B` formula in column D (Unrealised P/L) for every row
5. Sets up `=IF(B=0,0,ROUND(D/B*100,2))` formula in column E (P/L%) for every row
6. Applies alternating green/pink row colors
7. Adds the lavender "Month End Overall Profit/Loss %" summary row (E references last data row)
8. Creates the "Monthly Growth %" line chart to the right
9. Writes today's Invested and Current Value into the correct row

**You never need to create a new sheet or set up formulas manually again.**

---

## Security Summary

| Item | Where it lives | Rule |
|---|---|---|
| Username & password | `.env` on your local machine only | Never leave the machine |
| Service account JSON | Local folder, not in cloud sync | Script reads it at runtime only |
| Your investment amounts | Scraped on your machine → written directly to Sheet | No third party ever sees them |
| Log file | `logs/tracker.log` | Contains only dates and numbers, no credentials |

**Checklist before going live:**
- [ ] `.env` has your real credentials
- [ ] `.env` is in `.gitignore`
- [ ] Service account JSON is NOT in Google Drive / OneDrive / Dropbox
- [ ] You have NEVER typed your password into Claude or any AI chat
- [ ] `python tracker.py --dry-run` shows correct scraped values
- [ ] `python tracker.py` writes correct values to your Google Sheet
