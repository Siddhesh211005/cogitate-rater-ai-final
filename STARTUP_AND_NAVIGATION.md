# Startup And Navigation Guide

This file explains how to run the unified Cogitate Rater project locally, where to go in the browser, and how to test both the Excel and Schema rating paths.

## Project Location

```powershell
cd c:\Users\tanma\OneDrive\Desktop\laetscogiaiute\cogitate-rater-ai-final
```

The separate source Excel rater project is here:

```powershell
c:\Users\tanma\OneDrive\Desktop\laetscogiaiute\excel-rater\cogitate rater
```

Use the separate Excel rater project only as a reference/source of working workbooks and configs. The app to run is `cogitate-rater-ai-final`.

## Requirements

Install backend requirements into the same Python that runs Uvicorn:

```powershell
cd c:\Users\tanma\OneDrive\Desktop\laetscogiaiute\cogitate-rater-ai-final
python -m pip install -r backend\requirements.txt
```

Confirm the COM dependency is available:

```powershell
python -c "import pythoncom, win32com.client; print('pywin32 import ok')"
```

Install frontend requirements:

```powershell
cd c:\Users\tanma\OneDrive\Desktop\laetscogiaiute\cogitate-rater-ai-final\frontend
npm install
```

## Excel Setup

The Excel engine requires:

- Windows
- Microsoft Excel installed
- `pywin32` installed in the active Python environment
- Excel Trust Center allows the workbook folder

Recommended trusted local folders:

```text
cogitate-rater-ai-final\backend\uploads
cogitate-rater-ai-final\backend\raters
excel-rater\cogitate rater\templates
```

Excel path:

```text
Excel -> File -> Options -> Trust Center -> Trust Center Settings -> Trusted Locations -> Add new location
```

## Start Backend

From the project root:

```powershell
cd c:\Users\tanma\OneDrive\Desktop\laetscogiaiute\cogitate-rater-ai-final
uvicorn backend.main:app --reload --port 8000
```

Health check:

```text
http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok","engines":["schema","excel"],"version":"1.0.0"}
```

## Start Frontend

In a second terminal:

```powershell
cd c:\Users\tanma\OneDrive\Desktop\laetscogiaiute\cogitate-rater-ai-final\frontend
npm run dev
```

Open:

```text
http://127.0.0.1:3000
```

The frontend proxies `/api/*` to the FastAPI backend at `http://localhost:8000`.

## Navigation

Home:

```text
http://127.0.0.1:3000
```

Admin dashboard:

```text
http://127.0.0.1:3000/admin
```

Upload rater:

```text
http://127.0.0.1:3000/admin/upload
```

Client rater selection:

```text
http://127.0.0.1:3000/client
```

Client rater form:

```text
http://127.0.0.1:3000/client/{slug}
```

## Test Excel Engine

Known good workbook:

```text
excel-rater\cogitate rater\templates\mpl\template.xlsx
```

Manual UI flow:

1. Open `http://127.0.0.1:3000/admin/upload`.
2. Upload `excel-rater\cogitate rater\templates\mpl\template.xlsx`.
3. Choose `Excel Engine`.
4. Wait for warm status to become `ready`.
5. Click `Test Calculate`.
6. Confirm outputs appear.
7. Click `Test Download` to download a calculated workbook.
8. Click `Save Rater`.
9. Go to `http://127.0.0.1:3000/client`.
10. Open the saved rater and calculate again from the client panel.

Known smoke output for the MPL defaults:

```json
{
  "premium": 1667.952,
  "final_multiplier": 2.0849,
  "rating_multiple": 2.0048,
  "carrier_multiple": 0.75,
  "individual_risk": 0.75,
  "min_deductible": 10000
}
```

## Test Excel Engine From API

Use this quick script from the project root:

```powershell
@'
import time
from pathlib import Path
import requests

xlsx = Path(r"C:\Users\tanma\OneDrive\Desktop\laetscogiaiute\excel-rater\cogitate rater\templates\mpl\template.xlsx")
with xlsx.open("rb") as f:
    upload = requests.post(
        "http://127.0.0.1:8000/api/excel/upload",
        files={"file": ("template.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"name": "MPL API Smoke", "rater_type": "mpl"},
        timeout=30,
    )

print(upload.status_code, upload.json()["status"])
upload_id = upload.json()["upload_id"]
config = upload.json()["config"]

for _ in range(20):
    time.sleep(0.5)
    warm = requests.get(f"http://127.0.0.1:8000/api/excel/warm-status/{upload_id}", timeout=10)
    print(warm.json()["status"])
    if warm.json()["status"] == "ready":
        break

inputs = {field["field"]: field.get("default", "") for field in config["inputs"]}
calc = requests.post(
    "http://127.0.0.1:8000/api/excel/test-calculate",
    json={"upload_id": upload_id, "inputs": inputs},
    timeout=60,
)
print(calc.json()["outputs"])
'@ | python -
```

## Test Schema Engine

Manual UI flow:

1. Open `http://127.0.0.1:3000/admin/upload`.
2. Upload an `.xlsx` workbook.
3. Choose `Schema Engine`.
4. Review parsed config.
5. Save.
6. Open it from the client panel and calculate.

Important current limitation:

The Schema Engine can parse and route through the app, but formula coverage is not as reliable as native Excel COM. The MPL workbook currently returns `None` outputs through the Schema Engine, so use Excel Engine for real premium validation.

## Common Problems

### `pywin32 is not installed or Microsoft Excel COM is unavailable`

Install backend requirements into the active Python:

```powershell
python -m pip install -r backend\requirements.txt
python -c "import pythoncom, win32com.client; print('pywin32 import ok')"
```

Then restart Uvicorn.

### Warm status fails

Check:

- Excel is installed.
- The workbook can open manually in Excel.
- The workbook path is trusted in Excel Trust Center.
- No modal Excel prompt is blocking automation.
- Backend was restarted after installing `pywin32`.

### Client page says no raters

That means `backend/local_db/raters.json` has no saved raters yet. Upload and save from Admin first.

### Port already in use

Backend:

```powershell
Get-NetTCPConnection -LocalPort 8000
```

Frontend:

```powershell
Get-NetTCPConnection -LocalPort 3000
```

Stop the process using the port or start the service on another port.

## Verification Commands

Backend syntax check:

```powershell
python -m compileall backend
```

Frontend type check:

```powershell
cd frontend
npm run typecheck
```

Frontend lint:

```powershell
cd frontend
npm run lint
```

