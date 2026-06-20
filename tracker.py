"""
Finance First Services — Mutual Fund Tracker

Scrapes "Invested" and "Current Value" from the Finance First dashboard,
rounds both to the nearest integer, and writes them into the correct
row of the current month's Google Sheet worksheet.

CONFIRMED DOM structure:
  <div class="media-body">
    <h5 class="mt-0 pb-0">28,97,452.78</h5>   ← the number
    Current Value                               ← the label
  </div>

SHEET LAYOUT:
  Col A : blank spacer
  Col B : Date              e.g. "3 Jun", "20 Jun"
  Col C : Amount Invested   ← script writes integer here daily
  Col D : Current Mkt Value ← script writes integer here daily
  Col E : Unrealised P/L    =IF(OR(C{r}="",C{r}=0),"",D{r}-C{r})
  Col F : Profit/Loss %     =IF(OR(C{r}="",C{r}=0),"",ROUND((E{r}/C{r})*100,2))
  Row 1 : blank spacer (frozen)
  Row 2 : headers (frozen)
  Row 3+: one row per weekday
  Last+1: summary row
  Chart : col H, row 4, red line with data labels

Usage:
  python tracker.py            ← full daily run
  python tracker.py --dry-run ← scrape only, no sheet write
"""

import os, sys, re, time, logging, calendar, argparse
from datetime import datetime, date
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
import gspread
from google.oauth2.service_account import Credentials

load_dotenv()

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "tracker.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

LOGIN_URL  = os.getenv("LOGIN_URL", "")
USERNAME  = os.getenv("INVESTMENT_USERNAME", "")
PASSWORD  = os.getenv("INVESTMENT_PASSWORD", "")
SHEET_ID  = os.getenv("GOOGLE_SHEETS_ID", "")
SA_FILE   = os.getenv("SERVICE_ACCOUNT_FILE", "")

C_GREEN    = {"red": 0.851, "green": 0.918, "blue": 0.827}
C_PINK     = {"red": 0.918, "green": 0.820, "blue": 0.863}
C_LAVENDER = {"red": 0.788, "green": 0.855, "blue": 0.973}
C_HEADER   = {"red": 0.800, "green": 0.800, "blue": 0.800}
C_BLACK    = {"red": 0.000, "green": 0.000, "blue": 0.000}
C_TITLE    = {"red": 0.651, "green": 0.302, "blue": 0.475}
C_CHART_BG = {"red": 1.000, "green": 0.949, "blue": 0.800}
RED        = {"red": 1.000, "green": 0.000, "blue": 0.000}


# ══════════════════════════════════════════════════════════════════════════════
# SCRAPING
# ══════════════════════════════════════════════════════════════════════════════

def _parse_amount(raw: str) -> int:
    cleaned = re.sub(r"[₹,\s]", "", raw.strip())
    return round(float(cleaned))


def _extract_by_label(page, label: str):
    return page.evaluate(f"""
    () => {{
        for (const body of document.querySelectorAll('.media-body')) {{
            if ((body.innerText || '').includes('{label}')) {{
                const h5 = body.querySelector('h5.mt-0.pb-0');
                if (h5) return h5.innerText.trim();
            }}
        }}
        return null;
    }}
    """)


def scrape() -> dict:
    log.info("Launching browser → Finance First Services...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx     = browser.new_context(viewport={"width": 1280, "height": 900})
        page    = ctx.new_page()
        try:
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(2000)

            for sel in ["input[placeholder='Username']", "input[placeholder='username']",
                        "#username", "input[name='username']", "input[type='text']"]:
                try:
                    el = page.wait_for_selector(sel, timeout=2000)
                    if el and el.is_visible():
                        el.fill(USERNAME); log.info(f"Username: {sel}"); break
                except Exception: continue

            for sel in ["input[placeholder='Password']", "input[placeholder='password']",
                        "#password", "input[name='password']", "input[type='password']"]:
                try:
                    el = page.wait_for_selector(sel, timeout=2000)
                    if el and el.is_visible():
                        el.fill(PASSWORD); log.info(f"Password: {sel}"); break
                except Exception: continue

            for sel in ["button:has-text('Login')", "button[type='submit']",
                        "input[type='submit']", "#loginBtn"]:
                try:
                    el = page.query_selector(sel)
                    if el and el.is_visible():
                        el.click(); log.info(f"Login: {sel}"); break
                except Exception: continue

            try: page.wait_for_load_state("networkidle", timeout=20_000)
            except PWTimeout: pass
            page.wait_for_timeout(3000)
            log.info(f"Dashboard: {page.url}")

            current_raw  = _extract_by_label(page, "Current Value")
            invested_raw = _extract_by_label(page, "Invested")
            log.info(f"Raw → Current: {current_raw!r} | Invested: {invested_raw!r}")

            if not current_raw or not invested_raw:
                shot = os.path.join(LOG_DIR, "debug_screenshot.png")
                page.screenshot(path=shot, full_page=True)
                raise RuntimeError(f"Extraction failed. See {shot}")

            invested    = _parse_amount(invested_raw)
            current_val = _parse_amount(current_raw)
            log.info(f"Parsed → Invested: ₹{invested}  |  Current Value: ₹{current_val}")

            # ── Logout gracefully ─────────────────────────────────────────────
            try:
                # Step 1: Click profile icon to open the dropdown menu
                page.click("#profileMenuDropPanel")
                page.wait_for_timeout(800)

                # Step 2: Click the Logout link (id="logoutli")
                page.click("#logoutli")
                page.wait_for_timeout(1500)
                log.info("Logged out successfully.")
            except Exception as e:
                log.warning(f"Logout attempt failed (session may still be open): {e}")

            return {"invested": invested, "current_value": current_val}

        except Exception:
            try: page.screenshot(
                path=os.path.join(LOG_DIR, "error_screenshot.png"), full_page=True)
            except Exception: pass
            raise
        finally:
            ctx.close(); browser.close()


# ══════════════════════════════════════════════════════════════════════════════
# GOOGLE SHEETS
# ══════════════════════════════════════════════════════════════════════════════

def _sheets_client():
    creds = Credentials.from_service_account_file(SA_FILE, scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ])
    return gspread.authorize(creds)


def _weekdays_in_month(year, month):
    _, total = calendar.monthrange(year, month)
    return [date(year, month, d) for d in range(1, total+1)
            if date(year, month, d).weekday() < 5]


def _date_label(d):
    return f"{d.day} {d.strftime('%b')}"


def _rng(sid, r0, r1, c0, c1):
    return {"sheetId": sid, "startRowIndex": r0, "endRowIndex": r1,
            "startColumnIndex": c0, "endColumnIndex": c1}


def _fmt(sid, r0, r1, c0, c1, f):
    return {"repeatCell": {
        "range": _rng(sid, r0, r1, c0, c1),
        "cell":  {"userEnteredFormat": f},
        "fields": "userEnteredFormat(" + ",".join(f.keys()) + ")"
    }}


def _border(style="SOLID"):
    b = {"style": style, "color": C_BLACK}
    return {"top": b, "bottom": b, "left": b, "right": b}


def _fetch_chart_id(spreadsheet, sid):
    """Return chartId of the first chart on the given sheet, or None."""
    url  = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet.id}"
    data = spreadsheet.client.request(
        "get", url, params={"includeGridData": "false"}).json()
    for s in data.get("sheets", []):
        if s["properties"]["sheetId"] == sid:
            charts = s.get("charts", [])
            if charts:
                return charts[0]["chartId"]
    return None


def apply_chart_style(spreadsheet, sid, idx_data_f, idx_data_l):
    """
    Applies red color + data labels to the chart on the given sheet.
    Called as a SEPARATE step after _setup_worksheet completes,
    so the chart is fully committed server-side before we update it.
    """
    chart_id = _fetch_chart_id(spreadsheet, sid)
    if chart_id is None:
        log.warning("Chart not found — style not applied.")
        return

    log.info(f"Applying red color + data labels to chart {chart_id}...")
    RED = {"red": 1.0, "green": 0.0, "blue": 0.0}
    spec = {
        "title": "Monthly Growth %",
        "titleTextFormat": {"foregroundColor": C_TITLE, "bold": False},
        "backgroundColor":      C_CHART_BG,
        "backgroundColorStyle": {"rgbColor": C_CHART_BG},
        "hiddenDimensionStrategy": "SKIP_HIDDEN_ROWS_AND_COLUMNS",
        "basicChart": {
            "chartType":      "LINE",
            "legendPosition": "NO_LEGEND",
            "axis": [
                {"position": "BOTTOM_AXIS", "format": {"fontSize": 8}},
                {"position": "LEFT_AXIS",
                 "viewWindowOptions": {
                     "viewWindowMode": "EXPLICIT",
                     "viewWindowMin":  0,
                 }},
            ],
            "domains": [{"domain": {"sourceRange": {"sources": [{
                "sheetId":          sid,
                "startRowIndex":    idx_data_f,
                "endRowIndex":      idx_data_l,
                "startColumnIndex": 1,
                "endColumnIndex":   2,
            }]}}}],
            "series": [{
                "series": {"sourceRange": {"sources": [{
                    "sheetId":          sid,
                    "startRowIndex":    idx_data_f,
                    "endRowIndex":      idx_data_l,
                    "startColumnIndex": 5,
                    "endColumnIndex":   6,
                }]}},
                "targetAxis": "LEFT_AXIS",
                "color":      RED,
                "colorStyle": {"rgbColor": RED},
                "lineStyle":  {"width": 2, "type": "SOLID"},
                "dataLabel": {
                    "type":      "DATA",
                    "placement": "ABOVE",
                    "textFormat": {
                        "foregroundColor": RED,
                        "fontSize":        9,
                        "bold":            True,
                    },
                },
            }],
            "headerCount": 0,
        },
    }
    try:
        spreadsheet.batch_update({"requests": [
            {"updateChartSpec": {"chartId": chart_id, "spec": spec}}
        ]})
        log.info("✓ Chart updated — red line + data labels applied.")
    except Exception as e:
        log.error(f"updateChartSpec failed: {e}")


def _fetch_all_sheets_with_charts(spreadsheet):
    """
    Returns list of (sheet_title, sheet_id, chart_id, chart_spec) for every
    sheet that has at least one chart. Used to find a previous month's chart
    whose styling we can copy.
    """
    url  = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet.id}"
    data = spreadsheet.client.request(
        "get", url, params={"includeGridData": "false"}).json()
    result = []
    for s in data.get("sheets", []):
        charts = s.get("charts", [])
        if charts:
            result.append((
                s["properties"]["title"],
                s["properties"]["sheetId"],
                charts[0]["chartId"],
                charts[0]["spec"],
            ))
    return result


def _copy_style_from_previous_chart(spreadsheet, new_sid,
                                     new_chart_id, idx_data_f, idx_data_l):
    """
    Finds a previous month worksheet that has a chart, copies its spec,
    updates only the data source ranges to point to the new sheet,
    then applies it to the new chart via updateChartSpec.

    This is the most reliable way to get the correct red color + data labels
    because we are reusing a spec that Google has already accepted and stored.
    """
    sheets_with_charts = _fetch_all_sheets_with_charts(spreadsheet)

    # Exclude the new sheet itself — we want a DIFFERENT sheet's chart
    previous = [(t, s, c, sp) for t, s, c, sp in sheets_with_charts
                if s != new_sid]

    if not previous:
        log.warning("No previous month chart found to copy style from. "
                    "Manually style the first month's chart, then future "
                    "months will copy from it automatically.")
        return False

    # Use the most recently created one (first in list = most recently added tab)
    title, prev_sid, prev_chart_id, prev_spec = previous[0]
    log.info(f"Copying chart style from '{title}' (chartId={prev_chart_id})...")

    import copy, json
    spec = copy.deepcopy(prev_spec)

    # Update all sheetId and row/col range references to point to new sheet
    spec_str = json.dumps(spec)

    # Replace old sheetId with new sheetId throughout
    spec_str = spec_str.replace(str(prev_sid), str(new_sid))
    spec = json.loads(spec_str)

    # Update the data range row indices to match new sheet's data rows
    basic = spec.get("basicChart", {})

    # Update domains (X-axis: col B dates)
    for domain in basic.get("domains", []):
        for src in (domain.get("domain", {})
                          .get("sourceRange", {})
                          .get("sources", [])):
            src["startRowIndex"] = idx_data_f
            src["endRowIndex"]   = idx_data_l
            src["startColumnIndex"] = 1
            src["endColumnIndex"]   = 2

    # Update series (Y-axis: col F P/L%)
    for series in basic.get("series", []):
        for src in (series.get("series", {})
                          .get("sourceRange", {})
                          .get("sources", [])):
            src["startRowIndex"] = idx_data_f
            src["endRowIndex"]   = idx_data_l
            src["startColumnIndex"] = 5
            src["endColumnIndex"]   = 6

    # Force-inject red color + data labels into every series.
    # Google does not persist series styling in the stored spec,
    # so we must always set these explicitly regardless of what the
    # previous month's stored spec contains.
    RED = {"red": 1.0, "green": 0.0, "blue": 0.0}
    for series in spec.get("basicChart", {}).get("series", []):
        series["color"]      = RED
        series["colorStyle"] = {"rgbColor": RED}
        series["lineStyle"]  = {"width": 2, "type": "SOLID"}
        series["dataLabel"]  = {
            "type":      "DATA",
            "placement": "ABOVE",
            "textFormat": {
                "foregroundColor": RED,
                "fontSize":        9,
                "bold":            True,
            },
        }

    try:
        spreadsheet.batch_update({"requests": [
            {"updateChartSpec": {"chartId": new_chart_id, "spec": spec}}
        ]})
        log.info(f"✓ Chart style copied from '{title}' with red color + data labels.")
        return True
    except Exception as e:
        log.error(f"Style copy failed: {e}")
        return False


def _build_chart_spec(sid, idx_data_f, idx_data_l):
    """
    Build a complete chart spec from scratch.
    We never re-use the stored spec because Google omits the series
    from what it persists, causing 500 errors on updateChartSpec.
    """
    return {
        "title": "Monthly Growth %",
        "titleTextFormat": {"foregroundColor": C_TITLE, "bold": False},
        "backgroundColor": C_CHART_BG,
        "backgroundColorStyle": {"rgbColor": C_CHART_BG},
        "hiddenDimensionStrategy": "SKIP_HIDDEN_ROWS_AND_COLUMNS",
        "basicChart": {
            "chartType": "LINE",
            "legendPosition": "NO_LEGEND",
            "axis": [
                {"position": "BOTTOM_AXIS", "format": {"fontSize": 8}},
                {"position": "LEFT_AXIS",
                 "viewWindowOptions": {
                     "viewWindowMode": "EXPLICIT",
                     "viewWindowMin": 0,
                 }},
            ],
            "domains": [{"domain": {"sourceRange": {"sources": [{
                "sheetId":          sid,
                "startRowIndex":    idx_data_f,
                "endRowIndex":      idx_data_l,
                "startColumnIndex": 1,
                "endColumnIndex":   2,
            }]}}}],
            "series": [{
                "series": {"sourceRange": {"sources": [{
                    "sheetId":          sid,
                    "startRowIndex":    idx_data_f,
                    "endRowIndex":      idx_data_l,
                    "startColumnIndex": 5,
                    "endColumnIndex":   6,
                }]}},
                "targetAxis": "LEFT_AXIS",
                "color":      RED,
                "colorStyle": {"rgbColor": RED},
                "lineStyle":  {"width": 2, "type": "SOLID"},
                "dataLabel": {
                    "type":      "DATA",
                    "placement": "ABOVE",
                    "textFormat": {
                        "foregroundColor": RED,
                        "fontSize":        9,
                        "bold":            True,
                    },
                },
            }],
            "headerCount": 0,
        },
    }


def _setup_worksheet(ws, month_name):
    dt   = datetime.strptime(month_name, "%B %Y")
    days = _weekdays_in_month(dt.year, dt.month)
    n    = len(days)

    HEADER_ROW  = 2
    DATA_FIRST  = 3
    DATA_LAST   = DATA_FIRST + n - 1
    SUMMARY_ROW = DATA_LAST + 1

    IDX_HEADER  = HEADER_ROW - 1
    IDX_DATA_F  = DATA_FIRST - 1
    IDX_DATA_L  = DATA_LAST
    IDX_SUMMARY = SUMMARY_ROW - 1
    sid         = ws.id

    # Headers
    ws.update(values=[["Date", "Amount Invested", "Current Market Value",
                        "Unrealised Profit/Loss", "Profit/Loss %"]],
              range_name="B2:F2")

    # Data rows
    rows = []
    for i, d in enumerate(days):
        r = DATA_FIRST + i
        rows.append([
            "", _date_label(d), "", "",
            f'=IF(OR(C{r}="",C{r}=0),"",D{r}-C{r})',
            f'=IF(OR(C{r}="",C{r}=0),"",ROUND((E{r}/C{r})*100,2))',
        ])
    ws.update(values=rows, range_name=f"A{DATA_FIRST}:F{DATA_LAST}",
              value_input_option="USER_ENTERED")

    # Summary row
    ws.update(values=[["", "Month End Overall Profit/Loss %", "", "", "",
                        f"=F{DATA_LAST}"]],
              range_name=f"A{SUMMARY_ROW}:F{SUMMARY_ROW}",
              value_input_option="USER_ENTERED")

    # Formatting
    reqs = []
    reqs.append(_fmt(sid, IDX_HEADER, IDX_HEADER+1, 1, 6, {
        "backgroundColor": C_HEADER,
        "textFormat": {"bold": True, "fontSize": 12},
        "horizontalAlignment": "CENTER",
        "borders": _border("SOLID_MEDIUM"),
    }))
    for i in range(n):
        r0 = IDX_DATA_F + i
        reqs.append(_fmt(sid, r0, r0+1, 1, 6, {
            "backgroundColor": C_GREEN if i % 2 == 0 else C_PINK,
            "textFormat": {"fontSize": 10},
            "borders": _border(),
        }))
    for col in [2, 3, 4]:
        reqs.append(_fmt(sid, IDX_DATA_F, IDX_DATA_L, col, col+1,
                         {"numberFormat": {"type": "NUMBER", "pattern": "0"}}))
    reqs.append(_fmt(sid, IDX_DATA_F, IDX_DATA_L, 5, 6,
                     {"numberFormat": {"type": "NUMBER", "pattern": "0.00"}}))
    reqs.append(_fmt(sid, IDX_SUMMARY, IDX_SUMMARY+1, 1, 6, {
        "backgroundColor": C_LAVENDER,
        "textFormat": {"bold": True, "fontSize": 14},
        "horizontalAlignment": "CENTER",
        "borders": _border("SOLID_MEDIUM"),
    }))
    reqs.append({"mergeCells": {
        "range": _rng(sid, IDX_SUMMARY, IDX_SUMMARY+1, 1, 5),
        "mergeType": "MERGE_ALL",
    }})
    for ci, px in enumerate([30, 65, 155, 185, 220, 115, 40]):
        reqs.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": ci, "endIndex": ci+1},
            "properties": {"pixelSize": px}, "fields": "pixelSize",
        }})
    reqs.append({"updateSheetProperties": {
        "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 2}},
        "fields": "gridProperties.frozenRowCount",
    }})
    ws.spreadsheet.batch_update({"requests": reqs})

    # Step 1: Create chart (blue by default)
    ws.spreadsheet.batch_update({"requests": [{
        "addChart": {
            "chart": {
                "spec": {
                    "title": "Monthly Growth %",
                    "titleTextFormat": {"foregroundColor": C_TITLE, "bold": False},
                    "backgroundColor": C_CHART_BG,
                    "basicChart": {
                        "chartType": "LINE",
                        "legendPosition": "NO_LEGEND",
                        "axis": [
                            {"position": "BOTTOM_AXIS", "format": {"fontSize": 8}},
                            {"position": "LEFT_AXIS",
                             "viewWindowOptions": {
                                 "viewWindowMode": "EXPLICIT",
                                 "viewWindowMin": 0,
                             }},
                        ],
                        "domains": [{"domain": {"sourceRange": {"sources": [{
                            "sheetId": sid,
                            "startRowIndex": IDX_DATA_F, "endRowIndex": IDX_DATA_L,
                            "startColumnIndex": 1, "endColumnIndex": 2,
                        }]}}}],
                        "series": [{"series": {"sourceRange": {"sources": [{
                            "sheetId": sid,
                            "startRowIndex": IDX_DATA_F, "endRowIndex": IDX_DATA_L,
                            "startColumnIndex": 5, "endColumnIndex": 6,
                        }]}}, "targetAxis": "LEFT_AXIS"}],
                        "headerCount": 0,
                    },
                },
                "border": {"color": C_BLACK, "colorStyle": {"rgbColor": C_BLACK}},
                "position": {
                    "overlayPosition": {
                        "anchorCell": {"sheetId": sid, "rowIndex": 3, "columnIndex": 7},
                        "offsetXPixels": 10, "offsetYPixels": 10,
                        "widthPixels": 600, "heightPixels": 420,
                    }
                },
            }
        }
    }]})

    log.info(f"Worksheet '{ws.title}' structure complete. Chart color will be applied after.")


def _get_or_create_worksheet(spreadsheet, month_name):
    try:
        ws = spreadsheet.worksheet(month_name)
        log.info(f"Using existing worksheet: '{month_name}'")
        return ws
    except gspread.exceptions.WorksheetNotFound:
        log.info(f"Creating new worksheet: '{month_name}'")
        ws = spreadsheet.add_worksheet(title=month_name, rows=50, cols=20, index=0)
        _setup_worksheet(ws, month_name)

        # Write a flag file so run_tracker.bat knows to run fix_chart_color.py
        flag_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "new_sheet_created.flag")
        with open(flag_path, "w") as f:
            f.write(month_name)
        log.info(f"Flag written: new_sheet_created.flag ({month_name})")
        return ws


def write_to_sheet(invested: int, current_value: int, target_date: date = None):
    """
    Writes data to the sheet row matching target_date.
    If target_date is None, uses today's date.
    """
    entry_date = target_date or date.today()

    if entry_date.weekday() >= 5:
        log.info(f"{_date_label(entry_date)} is a weekend — Indian markets closed. Nothing written.")
        return

    client      = _sheets_client()
    spreadsheet = client.open_by_key(SHEET_ID)
    month_name  = entry_date.strftime("%B %Y")
    ws          = _get_or_create_worksheet(spreadsheet, month_name)
    date_str    = _date_label(entry_date)
    col_b       = ws.col_values(2)

    try:
        row = col_b.index(date_str) + 1
    except ValueError:
        log.error(f"'{date_str}' not found in col B of '{month_name}'. Market holiday?")
        return

    ws.update(values=[[invested, current_value]],
              range_name=f"C{row}:D{row}",
              value_input_option="USER_ENTERED")
    log.info(f"✓ Row {row} ({date_str}): Invested=₹{invested} | Current=₹{current_value}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def _validate_config():
    errors = []
    if not USERNAME: errors.append("INVESTMENT_USERNAME missing from .env")
    if not PASSWORD: errors.append("INVESTMENT_PASSWORD missing from .env")
    if not SHEET_ID: errors.append("GOOGLE_SHEETS_ID missing from .env")
    if not SA_FILE:  errors.append("SERVICE_ACCOUNT_FILE missing from .env")
    elif not os.path.exists(SA_FILE):
        errors.append(f"SERVICE_ACCOUNT_FILE not found: {SA_FILE!r}")
    if errors:
        for e in errors: log.error(e)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Scrape only — don't write to sheet")
    parser.add_argument("--date", type=str, default=None,
                        metavar="DD/MM/YYYY",
                        help="Optional: write scraped data to this date's row "
                             "instead of today. Format: DD/MM/YYYY e.g. 18/06/2026")
    args = parser.parse_args()

    # Parse --date if provided
    target_date = None
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%d/%m/%Y").date()
            log.info(f"Target date overridden to: {_date_label(target_date)} "
                     f"({target_date.strftime('%d/%m/%Y')})")
        except ValueError:
            log.error(f"Invalid --date format: {args.date!r}. Use DD/MM/YYYY e.g. 18/06/2026")
            sys.exit(1)

    log.info("=" * 60)
    log.info("Finance First Services Tracker — starting")
    _validate_config()

    data = scrape()

    if args.dry_run:
        log.info("DRY RUN — not writing to sheet.")
        log.info(f"  Invested      = ₹{data['invested']}")
        log.info(f"  Current Value = ₹{data['current_value']}")
        log.info(f"  P/L (approx)  = ₹{data['current_value'] - data['invested']}")
        if target_date:
            log.info(f"  Would write to: {_date_label(target_date)}")
    else:
        write_to_sheet(data["invested"], data["current_value"], target_date)

    log.info("Run complete.")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
