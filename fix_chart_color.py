"""
fix_chart_color.py
==================
Applies red color + data labels to the current month's chart.
Called automatically by tracker.py when a new month sheet is created.
Can also be run manually: python fix_chart_color.py
"""
import os, sys, json
from dotenv import load_dotenv

# Load .env from same directory as this script
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

SHEET_ID = os.getenv("GOOGLE_SHEETS_ID", "")
SA_FILE  = os.getenv("SERVICE_ACCOUNT_FILE", "")
# Sheet name passed as argument, or defaults to current month
MONTH_NAME = sys.argv[1] if len(sys.argv) > 1 else None

if not SHEET_ID or not SA_FILE:
    print("ERROR: GOOGLE_SHEETS_ID and SERVICE_ACCOUNT_FILE must be set in .env")
    sys.exit(1)

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import calendar

def weekdays_in_month(year, month):
    _, total = calendar.monthrange(year, month)
    from datetime import date
    return [date(year, month, d) for d in range(1, total+1)
            if date(year, month, d).weekday() < 5]

# Connect
creds = Credentials.from_service_account_file(SA_FILE, scopes=[
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
])
client      = gspread.authorize(creds)
spreadsheet = client.open_by_key(SHEET_ID)

# Determine which sheet to fix
if not MONTH_NAME:
    MONTH_NAME = datetime.today().strftime("%B %Y")

print(f"Fixing chart color for: {MONTH_NAME}")

# Find the sheet
try:
    ws = spreadsheet.worksheet(MONTH_NAME)
except Exception:
    print(f"ERROR: Worksheet '{MONTH_NAME}' not found.")
    sys.exit(1)

sid = ws.id

# Fetch chart ID
url  = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet.id}"
data = spreadsheet.client.request("get", url,
                                   params={"includeGridData": "false"}).json()
chart_id = None
for s in data.get("sheets", []):
    if s["properties"]["sheetId"] == sid:
        charts = s.get("charts", [])
        if charts:
            chart_id = charts[0]["chartId"]
        break

if not chart_id:
    print(f"ERROR: No chart found on '{MONTH_NAME}'.")
    sys.exit(1)

print(f"Found chart {chart_id} on sheet '{MONTH_NAME}' (sheetId={sid})")

# Compute data range
dt   = datetime.strptime(MONTH_NAME, "%B %Y")
days = weekdays_in_month(dt.year, dt.month)
n    = len(days)
idx_data_f = 2        # 0-based first data row (row 3)
idx_data_l = 2 + n    # 0-based exclusive end

# Build and send spec
RED = {"red": 1.0, "green": 0.0, "blue": 0.0}
spec = {
    "title": "Monthly Growth %",
    "titleTextFormat": {
        "foregroundColor": {"red": 0.651, "green": 0.302, "blue": 0.475},
        "bold": False,
    },
    "backgroundColor":      {"red": 1.0, "green": 0.949, "blue": 0.8},
    "backgroundColorStyle": {"rgbColor": {"red": 1.0, "green": 0.949, "blue": 0.8}},
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
    print(f"✓ Chart color fixed successfully for '{MONTH_NAME}'.")
    sys.exit(0)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
