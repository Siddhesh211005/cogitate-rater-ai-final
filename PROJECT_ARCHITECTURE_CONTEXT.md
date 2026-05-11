# Project Architecture Context

This file is the full working context for `cogitate-rater-ai-final`. It explains what the project is, how the folders fit together, which files matter, why those files exist, and what is complete versus still pending.

## What This Project Is

`cogitate-rater-ai-final` is a unified insurance rater platform. It combines two earlier systems:

- Schema Rater: parses workbook structure and tries to evaluate Excel formulas in Python.
- Excel Rater: uses real Microsoft Excel through COM automation for faithful workbook calculation.

The unified product has:

- One Next.js frontend.
- One FastAPI backend.
- One rater list.
- One dynamic client form component.
- Engine-specific backend calculation under the hood.

Admins upload Excel workbooks. Clients fill out generated forms and receive premium outputs without opening Excel.

## Current Runtime Stack

Frontend:

- Next.js App Router
- React
- TypeScript
- Tailwind/shadcn-style UI components

Backend:

- FastAPI
- Python
- `openpyxl` for workbook inspection and `_Schema` parsing
- `formulas` for the experimental Schema Engine
- `pywin32` plus Microsoft Excel COM for the Excel Engine

Storage:

- Local JSON fallback database in `backend/local_db`
- Local workbook persistence in `backend/raters`
- Azure CosmosDB and Azure Blob helper files exist, but local fallback is what makes development work immediately

## Top-Level Folders

```text
cogitate-rater-ai-final/
  backend/
  frontend/
  shared/
  STARTUP_AND_NAVIGATION.md
  PROJECT_ARCHITECTURE_CONTEXT.md
  EXCEL_WORKER_INTEGRATION_PLAN.md
  cogitate_context.md
  README.md
```

### `backend/`

Contains the single FastAPI backend.

Important folders:

```text
backend/
  main.py
  routers/
  engines/
  services/
  db/
  models/
  uploads/
  raters/
  local_db/
```

### `frontend/`

Contains the Next.js app.

Important folders:

```text
frontend/
  app/
  components/
  lib/
  package.json
  next.config.js
```

### `shared/`

Contains shared TypeScript types. This is a good place to consolidate config and rater shapes later.

## Backend Entry Point

File:

```text
backend/main.py
```

Why it exists:

- Creates the FastAPI app.
- Loads environment variables.
- Adds CORS.
- Mounts all routers.
- Provides health checks.

Mounted routers:

```python
app.include_router(schema.router, prefix="/api/schema")
app.include_router(excel.router, prefix="/api/excel")
app.include_router(raters.router, prefix="/api/raters")
```

Health endpoints:

```text
GET /health
GET /health/db
```

## Backend Routers

### `backend/routers/excel.py`

Purpose:

Handles the Excel COM engine workflow.

Main endpoints:

```text
POST /api/excel/upload
GET  /api/excel/warm-status/{upload_id}
POST /api/excel/handle-no-schema
POST /api/excel/test-calculate
POST /api/excel/test-download
POST /api/excel/save
POST /api/excel/calculate
GET  /api/excel/raters
GET  /api/excel/records
```

Why it matters:

This is the admin upload and test path for workbooks that should be calculated by real Excel. It saves the uploaded workbook locally, parses `_Schema`, starts a warm Excel worker, supports test calculation, supports download of a calculated workbook, then saves the rater to durable local storage and the rater metadata database.

Current behavior:

- Requires `_Schema` for normal Excel upload.
- If `_Schema` is missing, returns structured fallback options.
- Uses warm sessions to keep Excel open for fast test calculations.
- Saves workbooks to `backend/raters/{slug}/template.xlsx`.

### `backend/routers/schema.py`

Purpose:

Handles the Schema Engine workflow.

Main endpoints:

```text
POST /api/schema/upload
POST /api/schema/save
POST /api/schema/calculate
GET  /api/schema/raters
DELETE /api/schema/raters/{rater_id}
```

Why it matters:

This route keeps the non-COM path available. It is useful for simpler workbooks and for experiments with inferred schemas.

Current limitation:

The Schema Engine is not reliable enough for complex or production premium validation. It can route and save, but many real workbook formulas return `None` through the Python formula path.

### `backend/routers/raters.py`

Purpose:

Unified client-facing rater API.

Main endpoints:

```text
GET  /api/raters/
GET  /api/raters/{slug}/config
POST /api/raters/{slug}/calculate
GET  /api/raters/{slug}/records
GET  /api/raters/{slug}/records/{record_id}
DELETE /api/raters/{rater_id}
```

Why it matters:

The frontend client panel does not need to know which engine a rater uses. It loads a rater by slug, renders the stored config, posts inputs, and this router dispatches to either:

- `engines.schema_engine.calculate`
- `engines.excel_engine.calculate`

It also writes execution records after calculation.

## Backend Engines

### `backend/engines/excel_worker.py`

Purpose:

Runs Microsoft Excel COM automation inside a dedicated worker thread.

Why it exists:

Excel COM must be initialized and used from the same thread. The worker owns the Excel app and workbook instance, while FastAPI communicates through queues.

Key responsibilities:

- Calls `pythoncom.CoInitialize()`.
- Starts Excel with `win32com.client.DispatchEx("Excel.Application")`.
- Opens workbook read-only.
- Writes input values to configured cells.
- Calls `Excel.Application.Calculate()`.
- Reads output cells.
- Optionally saves a calculated workbook copy.
- Closes workbook and quits Excel on shutdown.

Important design:

All Excel calls stay inside the worker thread. Request threads do not directly touch COM objects.

### `backend/engines/excel_engine.py`

Purpose:

Provides a clean wrapper around Excel workers.

Important functions:

```python
prime_upload_session(upload_id, workbook_path, config)
run_upload_warmup(upload_id, workbook_path, config)
calculate_for_upload_session(upload_id, inputs, keep_file=False)
calculate_from_file(workbook_path, config, inputs, keep_file=False)
calculate(rater, inputs, keep_file=False)
resolve_workbook_path(rater)
shutdown_upload_session(upload_id)
```

Why it exists:

Routers should not know worker internals. They should ask the engine to prime, calculate, persist, or shut down.

### `backend/engines/schema_engine.py`

Purpose:

Attempts to calculate workbooks without Excel using Python libraries.

How it works:

- Opens workbook with `openpyxl`.
- Writes inputs to configured cells.
- Saves to a temp file.
- Tries to evaluate with `formulas`.
- Falls back to `openpyxl` cached values.

Current limitation:

This does not fully reproduce Excel for many real raters. For the known MPL workbook, it currently returns `None` outputs, while Excel COM returns real values.

## Backend Services

### `backend/services/schema_parser.py`

Purpose:

Creates the engine-neutral config used by both backend and frontend.

Important functions:

```python
check_schema_sheet(filepath)
parse_schema(filepath, require_schema_sheet=False)
auto_generate_schema(filepath)
```

Config shape:

```json
{
  "sheet": "Rater",
  "inputs": [
    {
      "field": "state_of_risk",
      "cell": "B11",
      "type": "dropdown",
      "label": "State of Risk",
      "group": "Rating Inputs",
      "options": ["CO", "CA"],
      "default": "CO"
    }
  ],
  "outputs": [
    {
      "field": "premium",
      "cell": "B40",
      "type": "number",
      "label": "Total Premium",
      "group": "Results",
      "primary": true
    }
  ]
}
```

Why `_Schema` matters:

The Excel Engine needs a mapping from form fields to workbook cells. `_Schema` provides that mapping in a workbook-owned way.

Supported `_Schema` columns:

```text
field
cell
type
label
direction
group
options
default
primary
```

### `backend/services/warm_session.py`

Purpose:

Stores in-memory upload sessions and active Excel workers.

Why it exists:

Admin upload/test flow benefits from a warm workbook instance. Without this, every test calculation would start Excel, open the workbook, calculate, close Excel, and feel slow.

Important concepts:

- Upload sessions are temporary.
- Template/live rater workers are pooled.
- Old upload sessions expire after `SESSION_TTL_SECONDS`.
- Active operations are locked so overlapping test/download calls do not collide.

### `backend/services/nim_enrichment.py`

Purpose:

Placeholder/service area for NVIDIA NIM label enrichment. This is intended for upload-time schema enrichment, replacing the older Gemini idea.

Current status:

Present as part of the planned architecture, not core to the Excel smoke path.

## Backend Database Layer

### `backend/db/cosmos.py`

Purpose:

Provides storage operations for raters, records, and sessions.

Why it exists:

The target production architecture uses Azure CosmosDB, but local development should work without Azure. This file tries Cosmos first and falls back to local JSON files.

Local files:

```text
backend/local_db/raters.json
backend/local_db/records.json
backend/local_db/sessions.json
```

Important functions:

```python
create_rater(...)
list_raters(...)
get_rater_by_slug(slug)
delete_rater(...)
create_record(...)
list_records(rater_slug)
create_session(...)
```

### `backend/db/blob.py`

Purpose:

Azure Blob helper for workbook binary storage.

Why it exists:

Production should store `.xlsx` binaries in Blob Storage, not in CosmosDB.

Current status:

The helper exists, but the working local path currently stores durable workbooks under:

```text
backend/raters/{slug}/template.xlsx
```

Blob download-to-local-before-COM is still a production hardening task.

## Frontend App Routes

### `frontend/app/page.tsx`

Purpose:

Home/splash page. It sends users to Admin Portal or Client Panel.

### `frontend/app/admin/page.tsx`

Purpose:

Admin dashboard.

Behavior:

- Calls `GET /api/raters/`.
- Shows saved raters.
- Shows engine badge to admins.
- Allows delete.
- Links to upload flow.

### `frontend/app/admin/upload/page.tsx`

Purpose:

Admin upload/review/test/save flow.

Flow:

1. Drop workbook.
2. Choose `Schema Engine` or `Excel Engine`.
3. Upload and parse.
4. For Excel, wait for warm status.
5. Review parsed inputs and outputs.
6. Test calculate.
7. Test download calculated workbook.
8. Save rater.

Important backend calls:

```text
POST /api/excel/upload
GET  /api/excel/warm-status/{upload_id}
POST /api/excel/test-calculate
POST /api/excel/test-download
POST /api/excel/save
POST /api/schema/upload
POST /api/schema/save
```

### `frontend/app/client/page.tsx`

Purpose:

Client rater picker.

Behavior:

- Calls `GET /api/raters/`.
- Shows saved raters without exposing engine details.
- Links to `/client/{slug}`.

### `frontend/app/client/[slug]/page.tsx`

Purpose:

Client dynamic rating form.

Behavior:

- Calls `GET /api/raters/{slug}/config`.
- Seeds form defaults.
- Renders inputs with `RatingForm`.
- Posts calculation to `POST /api/raters/{slug}/calculate`.
- Displays results with `ResultsDashboard`.

## Frontend Components

### `frontend/components/EngineSelector/index.tsx`

Purpose:

Lets admin choose between Schema Engine and Excel Engine during upload.

Why it exists:

Engine choice is an admin decision, not a client concern.

### `frontend/components/NoSchemaFallback/index.tsx`

Purpose:

Shown when admin chooses Excel Engine but workbook has no `_Schema` sheet.

Options:

- Auto-generate schema.
- Switch to Schema Engine.
- Upload `_Schema` manually.

Current recommended path:

Manual `_Schema` is still the reliable path for real raters.

### `frontend/components/RatingForm/index.tsx`

Purpose:

Renders an engine-neutral dynamic form from stored config.

Why it matters:

Both engines produce the same config format, so the client UI does not need engine-specific forms.

### `frontend/components/ResultsDashboard/index.tsx`

Purpose:

Displays primary and secondary output values after calculation.

## Important Data Flow

### Excel Admin Upload Flow

```text
Admin UI
  -> POST /api/excel/upload
  -> save workbook to backend/uploads/{upload_id}.xlsx
  -> parse _Schema
  -> create warm session
  -> start Excel worker in background
  -> frontend polls /api/excel/warm-status/{upload_id}
  -> admin test calculates
  -> admin saves
  -> workbook copied to backend/raters/{slug}/template.xlsx
  -> rater metadata saved to backend/local_db/raters.json
```

### Excel Client Calculate Flow

```text
Client UI
  -> GET /api/raters/{slug}/config
  -> render dynamic form
  -> POST /api/raters/{slug}/calculate
  -> unified router loads rater by slug
  -> sees engine = excel
  -> excel_engine resolves workbook path
  -> ExcelWorker writes inputs and calculates
  -> outputs returned
  -> record saved to backend/local_db/records.json
```

### Schema Flow

```text
Admin UI
  -> POST /api/schema/upload
  -> parse or infer config
  -> save rater
Client UI
  -> POST /api/raters/{slug}/calculate
  -> unified router sees engine = schema
  -> schema_engine attempts Python formula calculation
```

## Workbooks And Rater Compatibility

Known working Excel smoke workbook:

```text
excel-rater\cogitate rater\templates\mpl\template.xlsx
```

Recommended engine by rater:

```text
MPL with _Schema: Excel Engine works and is currently validated.
MPL without _Schema: Schema Engine can parse, but Excel needs manual _Schema for reliable output.
Homeowners: Excel Engine preferred because formula chains are complex.
Excess Follow Form: Excel Engine required because it is multi-sheet and sequential.
PAR Model: Excel Engine needed, but true batch UI/API is still pending.
```

## Current Verified Result

After installing requirements, the Excel COM path was tested successfully.

Known MPL default outputs:

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

API path also passed:

```text
POST /api/excel/upload -> 200 ok
GET /api/excel/warm-status/{upload_id} -> ready
POST /api/excel/test-calculate -> 200 ok, warm_used true
```

## What Is Done

- Single FastAPI app exists.
- Next.js frontend exists.
- Excel worker integration exists.
- `pywin32` dependency installed into the active backend Python.
- Excel COM direct smoke test passes.
- Excel upload/warm/test-calculate API smoke test passes.
- `_Schema` parser works for MPL.
- Unified `/api/raters` dispatcher works structurally.
- Local JSON database fallback exists.
- Admin upload page supports test calculate and test download.
- Client page loads config and calculates through unified endpoint.
- Frontend typecheck and lint pass.
- Backend compile check passes.

## What Is Left

High priority:

- Test full save -> client calculate flow from the UI with the MPL workbook.
- Validate Homeowners and other complex workbooks after adding or confirming clean configs.
- Improve Schema Engine if it must produce production-grade outputs.

Medium priority:

- Add `/api/raters/{slug}/calculate-and-download` in the unified router for saved Excel raters.
- Return calculated workbook download links from client calculations.
- Add automated backend tests for `_Schema` parsing and dispatcher payload shape.
- Add Windows-only tests for Excel COM.

Production hardening:

- Store original workbooks in Azure Blob.
- Download blob workbook to local temp before COM calculation.
- Store execution workbook copies in Blob.
- Add authentication/authorization.
- Add structured logging and request IDs.
- Add worker shutdown cleanup on FastAPI shutdown.
- Add PAR batch endpoint and batch UI.

## Development Rules For Future Work

- Keep Excel COM calls inside `ExcelWorker`.
- Do not calculate directly from a blob URL; COM needs a local workbook path.
- Do not silently switch engines. Engine behavior affects premium results.
- Keep the config format engine-neutral.
- Admins can see engine badges; clients should not need to care.
- Use the Excel Engine for real premium validation until Schema Engine is proven.

