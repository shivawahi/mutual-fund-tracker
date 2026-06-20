# 📈 Mutual Fund Tracker

An automated tool that scrapes daily mutual fund portfolio data from **Finance First Services** and logs it into a **Google Sheet** — eliminating the need for manual data entry every day.

---

## What It Does

Every weekday at **10:00 AM IST**, the tracker automatically:

1. Logs into the Finance First Services investor portal
2. Reads the **Invested** and **Current Market Value** amounts from the dashboard
3. Rounds both values to the nearest integer
4. Finds today's row in the current month's Google Sheet worksheet
5. Writes the data — columns D & E auto-calculate Unrealised Profit/Loss and Profit/Loss %
6. Logs out gracefully from the portal
7. Sends an **email report** with the execution status and logs

---

## Google Sheet Structure

Each month gets its own worksheet (e.g. `June 2026`) with:

- All weekdays of the month pre-filled (weekends excluded — Indian markets closed)
- Alternating row colors for easy reading
- Auto-calculated Unrealised Profit/Loss and Profit/Loss % columns
- A **Monthly Growth %** line chart showing portfolio performance across the month
- A summary row showing the month-end overall Profit/Loss %

---

## How It Runs

The tracker runs automatically via **GitHub Actions** — no laptop or server needs to be running. It executes on GitHub's cloud infrastructure on a daily schedule.

It can also be triggered **manually** from the GitHub Actions tab for any specific date — useful for backfilling missed days.

---

## Notifications

After every run, an email is sent with:

- ✅ Success or ❌ Failure status
- Last 50 lines of the execution log
- Direct link to the full run details on GitHub

---

## Security

- All credentials (portal login, Google Sheets API, email) are stored as **encrypted GitHub Secrets** — never in the code
- The Google Sheet is accessed via a dedicated service account with Editor access only to that specific sheet
- No sensitive information exists anywhere in this repository

---

## Setup

See **SETUP_GUIDE.md** and **GITHUB_SETUP.md** in this repository for full setup instructions.
