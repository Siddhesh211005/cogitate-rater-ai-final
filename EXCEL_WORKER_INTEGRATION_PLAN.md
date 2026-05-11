# Excel Worker Integration Plan

## Goal

Integrate the working Excel COM calculation engine from:

```text
excel-rater/cogitate rater/backend/
```

into:

```text
cogitate-rater-ai-final/backend/
```

The target result is that `cogitate-rater-ai-final` can upload, parse, warm, test, save, calculate, and optionally download calculated Excel workbooks using the same reliable `win32com` worker pattern from the Excel rater project.

This plan treats the Excel rater project as the source of truth for Excel execution.

## Current State

### In `cogitate-rater-ai-final`

The unified project already has:

- FastAPI app with routers:
  - `backend/routers/excel.py`
  - `backend/routers/schema.py`
  - `backend/routers/raters.py`
- CosmosDB helper:
  - `backend/db/cosmos.py`
- Blob helper:
  - `backend/db/blob.py`
- Schema parser:
  - `backend/services/schema_parser.py`
- Placeholder schema engine:
  - `backend/engines/schema_engine.py`

But it is missing:

- `backend/engines/excel_engine.py`
- A real COM worker implementation
- Correct warm session lifecycle
- Correct workbook file/blob handling
- Correct frontend/backend response shape alignment

### In `excel-rater/cogitate rater`

The Excel rater has the real working pieces:

- `backend/engine.py`
- `backend/excel_worker.py`
- `backend/warm_sessions.py`
- `backend/schema_parser.py`
- Admin upload/test/save logic in `backend/main.py`

The most important implementation pattern is:

1. Open Excel with `win32com.client.DispatchEx("Excel.Application")`.
2. Open workbook in a dedicated worker thread.
3. Keep workbook warm while admin tests or while live rater is used.
4. Write input fields into mapped cells.
5. Call `Excel.Application.Calculate()`.
6. Read mapped output cells.
7. Optionally save a calculated workbook copy with `SaveCopyAs`.

## Phase 1: Add Excel Engine Files

### Files To Add

Create these files in `cogitate-rater-ai-final/backend/engines/`:

```text
backend/engines/excel_engine.py
backend/engines/excel_worker.py
```

Create or replace this service:

```text
backend/services/warm_session.py
```

The existing `warm_session.py` has a Cosmos-oriented async design but is not currently wired correctly and imports a missing `get_container`. For the first working integration, use the proven in-memory worker registry from the Excel rater project, then later persist session metadata to Cosmos.

### Implementation Notes

`excel_worker.py` should be ported almost directly from the Excel rater project.

Keep:

- `ExcelWorker(threading.Thread)`
- `pythoncom.CoInitialize()`
- `win32com.client.DispatchEx("Excel.Application")`
- `Workbooks.Open(..., ReadOnly=True, UpdateLinks=0, IgnoreReadOnlyRecommended=True, CorruptLoad=1)`
- `_write_cell()`
- `_read_cell()`
- `_do_calculation()`
- `calculate_sync()`
- `shutdown()`

`excel_engine.py` should expose a clean unified API:

```python
def prime_upload_session(upload_id: str, workbook_path: Path, config: dict) -> dict
def calculate_for_upload_session(upload_id: str, inputs: dict, keep_file: bool = False) -> tuple[dict, dict]
def calculate_from_file(workbook_path: Path, config: dict, inputs: dict, keep_file: bool = False) -> tuple[dict, dict]
def calculate(rater: dict, inputs: dict, keep_file: bool = False) -> tuple[dict, dict]
def shutdown_upload_session(upload_id: str) -> None
```

## Phase 2: Normalize Config Format

The unified config must support both simple cells and cross-sheet cells.

Required field shape:

```json
{
  "field": "premium",
  "cell": "B40",
  "type": "number",
  "label": "Total Premium",
  "group": "Results",
  "primary": true
}
```

Also support cross-sheet cells:

```json
{
  "field": "premium_rate",
  "cell": "'Inputs & Outputs'!H4",
  "type": "number",
  "label": "Premium Rate"
}
```

### Parser Changes

Update `backend/services/schema_parser.py` so `_Schema` parsing matches the Excel rater parser:

- Require `_Schema` for Excel engine upload.
- Read columns:
  - `field`
  - `cell`
  - `type`
  - `label`
  - `direction`
  - `group`
  - `options`
  - `default`
- Split dropdown options by `;`.
- Convert numeric options/defaults when appropriate.
- Mark first output as primary if none is marked.
- Preserve `sheet`.
- Inject schedule mode if contiguous schedule rows are detected.

### Risk

Some workbooks may not have a clean `_Schema`.

### Handling

If `_Schema` is missing:

- Return `status: "no_schema"`.
- Do not silently switch engines.
- Frontend should show the existing fallback options:
  - auto-generate schema
  - switch to schema engine
  - upload `_Schema` manually

For the first integration, make manual `_Schema` the reliable path and keep auto-generation as a later enhancement.

## Phase 3: Fix Workbook Storage Strategy

The Excel worker cannot calculate from a raw Azure Blob URL. It needs a local `.xlsx` path.

### Upload Flow

On admin upload:

1. Save uploaded workbook locally:

```text
backend/uploads/{upload_id}.xlsx
```

2. Parse `_Schema`.
3. Create warm session with local workbook path.
4. Optionally upload original workbook to Blob for persistence later.

### Save Flow

On admin save:

1. Stop/release warm worker for that upload.
2. Copy local workbook to durable storage:
   - short-term: keep local path under `backend/raters/{slug}/template.xlsx`
   - long-term: upload to Azure Blob
3. Save rater metadata/config in CosmosDB.
4. Store either:
   - `workbook_local_path` for local dev
   - `workbook_blob_url` for production

Recommended document shape:

```json
{
  "id": "uuid",
  "slug": "mpl-old-republic",
  "name": "MPL Old Republic",
  "engine": "excel",
  "rater_type": "mpl",
  "config": {},
  "workbook_local_path": "backend/raters/mpl-old-republic/template.xlsx",
  "workbook_blob_url": "",
  "has_schema_sheet": true,
  "meta": {}
}
```

### Risk

The current unified `create_rater()` defaults `workbook_blob_url=""`, which makes calculation fail.

### Handling

Change the rater document model and helper to require at least one resolvable workbook location.

Add a helper:

```python
def resolve_workbook_path(rater: dict) -> Path:
    if workbook_local_path exists:
        return Path(workbook_local_path)
    if workbook_blob_url exists:
        download blob to temp file and return temp path
    raise FileNotFoundError
```

## Phase 4: Replace Excel Router Flow

Update:

```text
backend/routers/excel.py
```

### Upload Endpoint

`POST /api/excel/upload`

Should:

1. Validate `.xlsx`.
2. Save to `backend/uploads/{upload_id}.xlsx`.
3. Check `_Schema`.
4. If missing, return no-schema fallback response.
5. Parse config.
6. Create warm session.
7. Start background warm prime.
8. Return:

```json
{
  "status": "ok",
  "upload_id": "...",
  "engine": "excel",
  "config": {},
  "warm_status": "warming"
}
```

### Warm Status Endpoint

`GET /api/excel/warm-status/{upload_id}`

Should return:

```json
{
  "upload_id": "...",
  "status": "warming | ready | failed | expired | missing",
  "engine": "excel",
  "parsed_config": {},
  "error_message": null
}
```

### Test Calculate Endpoint

`POST /api/excel/test-calculate`

Input:

```json
{
  "upload_id": "...",
  "inputs": {}
}
```

Should use the warm upload worker.

Return:

```json
{
  "status": "ok",
  "outputs": {},
  "warm_used": true,
  "timings": {}
}
```

### Test Download Endpoint

Add:

```text
POST /api/excel/test-download
```

This should calculate with `keep_file=True` and return `FileResponse`.

### Save Endpoint

`POST /api/excel/save`

Input:

```json
{
  "upload_id": "...",
  "slug": "...",
  "name": "...",
  "rater_type": "custom",
  "config": {}
}
```

Should:

1. Validate slug.
2. Ensure no duplicate slug.
3. Shut down upload worker.
4. Persist workbook locally and/or to Blob.
5. Create Cosmos rater document.
6. Delete upload temp file if no longer needed.

## Phase 5: Fix Unified Raters Dispatcher

Update:

```text
backend/routers/raters.py
```

### Config Endpoint

Currently it returns:

```json
{ "status": "ok", "rater": {...} }
```

Frontend in `cogitate-rater-ai-final` expects `data.config`.

Pick one contract. Recommended:

```json
{
  "status": "ok",
  "rater": {},
  "config": {}
}
```

### Calculate Endpoint

Current function signature:

```python
def calculate(slug: str, inputs: dict)
```

But frontend posts:

```json
{ "inputs": {} }
```

Fix by reading payload:

```python
payload = await request.json()
inputs = payload.get("inputs", payload)
```

For Excel:

```python
from engines.excel_engine import calculate
outputs, meta = calculate(rater, inputs)
```

Then write record to Cosmos:

```python
create_record(...)
```

Return:

```json
{
  "status": "ok",
  "slug": "...",
  "engine": "excel",
  "outputs": {},
  "timings": {}
}
```

## Phase 6: Frontend Contract Fixes

Update:

```text
frontend/app/admin/upload/page.tsx
frontend/app/client/[slug]/page.tsx
```

### Admin Upload Page

Fix these mismatches:

- Send `name` and `rater_type` if backend requires them, or make backend defaults optional.
- Poll `/api/excel/warm-status/{id}` only for Excel uploads.
- For schema upload, either add schema warm endpoint or skip warm polling.
- Save to `/api/excel/save` only when engine is Excel.
- Save to `/api/schema/save` when engine is Schema.
- Include `slug` in save payload.
- For no-schema fallback, call `/api/excel/handle-no-schema` instead of re-uploading with an ignored flag.

### Client Rater Page

Fix config loading:

```ts
setConfig(data.config ?? data.rater?.config)
```

Fix calculate response handling:

```ts
setOutputs(data.outputs)
setDownloadUrl(data.download_url ?? null)
```

## Phase 7: Error Handling Plan

### Excel Not Installed

Likely error:

```text
Invalid class string
Excel.Application not found
```

Handling:

- Return HTTP 503.
- Message: "Microsoft Excel is not installed or COM automation is unavailable."
- Frontend should show a clear admin-only error.

### Excel File Locked

Likely error:

```text
0x800A03EC
```

Handling:

- Open workbooks with `ReadOnly=True`.
- Use `DispatchEx` per worker.
- On save, shut down the upload worker before copying/deleting workbook.
- Sleep briefly after shutdown if needed.

### COM Threading Failure

Likely cause:

- Missing `pythoncom.CoInitialize()` in worker thread.

Handling:

- Keep all COM calls inside `ExcelWorker.run()`.
- Never use COM workbook/app from FastAPI request thread.
- Use queues for request/response.

### Calculation Timeout

Likely cause:

- Large workbook, circular refs, broken external link.

Handling:

- Add timeout in `calculate_sync`.
- Return HTTP 504 for timeout.
- Include workbook slug/upload_id in logs.
- Optionally expose timing metrics.

### Formula External Links Or Prompts

Likely cause:

- Workbook has external links, corrupt repair prompt, read-only prompt.

Handling:

Use:

```python
Workbooks.Open(
    path,
    UpdateLinks=0,
    ReadOnly=True,
    IgnoreReadOnlyRecommended=True,
    CorruptLoad=1,
)
```

Also set:

```python
app.DisplayAlerts = False
app.Visible = False
```

### Missing `_Schema`

Handling:

- Return structured no-schema response.
- Do not silently switch engines.
- Allow admin to upload corrected workbook.

### Bad Cell Reference

Examples:

```text
B999999
'Wrong Sheet'!H4
```

Handling:

- Validate config during upload by checking every mapped input/output cell.
- Return all invalid cells in one response.

### Type Conversion Problems

Examples:

- User sends `"abc"` for number field.
- Dropdown numeric option arrives as string.

Handling:

- `_coerce_by_type()` should convert numbers when possible.
- If conversion fails, write original value and let workbook validations/formulas handle it.
- For strict mode later, reject invalid numbers at API boundary.

### Warm Session Expired

Handling:

- If upload session expired, return 404/410 and ask admin to re-upload.
- Do not attempt to calculate with a missing temp workbook.

### Worker Memory Leak

Risk:

- Excel processes stay running after errors.

Handling:

- Always call `wb.Close(SaveChanges=False)` and `app.Quit()` in `finally`.
- Add shutdown endpoint or app shutdown hook later.
- Expire old sessions periodically.

### Concurrent Requests

Risk:

- Same workbook worker receives overlapping requests.

Handling:

- Worker already serializes requests through queue.
- Upload session uses active operation lock.
- Template/live raters can use worker pool of 2-4 workers.

## Phase 8: Validation And Tests

### Backend Tests

Add tests for:

- `_Schema` parsing.
- Missing `_Schema`.
- Numeric option/default parsing.
- Cross-sheet cell parsing.
- Bad config validation.
- Rater dispatcher payload shape.
- Save requires slug.

COM-specific tests should be marked Windows-only.

### Manual Smoke Test

1. Start backend:

```bash
uvicorn backend.main:app --reload --port 8000
```

2. Start frontend:

```bash
cd frontend
npm run dev
```

3. Upload MPL workbook with `_Schema`.
4. Confirm warm status becomes ready.
5. Test calculate.
6. Test download.
7. Save rater.
8. Open client panel.
9. Select saved rater.
10. Calculate premium.
11. Confirm record is written.

### Expected First Stable Target

MPL should work first.

Then test:

- PAR model cross-sheet outputs.
- Homeowners large config.
- Any schedule-mode workbook.

## Phase 9: Production Hardening

After the local COM path works:

1. Persist original workbooks to Azure Blob.
2. Download Blob workbooks to local temp before COM calculation.
3. Store execution records in Cosmos.
4. Store calculated workbook copies in Blob.
5. Add app shutdown cleanup for worker pools.
6. Add authentication/authorization.
7. Restrict CORS.
8. Add structured logging.
9. Add request IDs.
10. Add admin-visible Excel engine health check.

## Recommended Build Order

1. Copy `excel_worker.py` into unified backend.
2. Build `excel_engine.py` wrapper.
3. Replace/fix warm session service with in-memory worker registry.
4. Fix `_Schema` parser to match Excel rater behavior.
5. Rewrite `backend/routers/excel.py` around upload, warm status, test calculate, test download, save.
6. Fix `backend/routers/raters.py` dispatcher response shapes.
7. Fix frontend admin upload/save/test calls.
8. Fix frontend client config response handling.
9. Run MPL smoke test.
10. Add records/download support.
11. Add Blob/Cosmos production persistence.

## Definition Of Done

The integration is complete when:

- `backend/engines/excel_engine.py` exists and is used.
- Excel upload with `_Schema` returns parsed config.
- Warm status reaches `ready`.
- Test calculate returns real Excel COM outputs.
- Test download returns a calculated workbook.
- Save creates a durable rater document with workbook location.
- Client calculate dispatches through `/api/raters/{slug}/calculate`.
- Execution record is saved.
- Missing `_Schema`, Excel COM failure, timeout, and bad slug errors are handled clearly.

