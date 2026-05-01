# Cogitate Unified Rater Engine

A unified insurance premium rating platform that consolidates two separately built rater systems (Schema Rater + Excel Rater) into a single product with one UI, one backend, and one database.

## Architecture

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router) |
| Backend | FastAPI (Python 3.11+) |
| Formula Engine A | Python `formulas` library |
| Formula Engine B | `win32com` Excel COM (Windows only) |
| LLM Enrichment | NVIDIA NIM API |
| Database | Azure CosmosDB |
| File Storage | Azure Blob Storage |

## Prerequisites

- Windows (required for Excel COM engine)
- Python 3.11+
- Node.js 18+
- Microsoft Excel installed
- Azure account (CosmosDB + Blob Storage)
- NVIDIA Developer Program account (free NIM API key)
- Azure CosmosDB Emulator (for local development)

## Project Structure
cogitate-unified/
├── backend/
│   ├── routers/          # FastAPI route handlers
│   ├── engines/          # Schema + Excel calculation engines
│   ├── services/         # Schema parser, warm session, NIM enrichment
│   ├── db/               # CosmosDB + Blob Storage clients
│   ├── models/           # Pydantic models
│   └── main.py
├── frontend/
│   ├── app/              # Next.js App Router pages
│   └── components/       # Shared UI components
└── shared/
└── types/

## Local Development Setup

### 1. Clone and create virtual environment

```bash
git clone <repo>
cd cogitate-rater-ai-final
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install backend dependencies

```bash
cd backend
pip install -r requirements.txt
python C:\Users\<you>\.venv\Scripts\pywin32_postinstall.py -install
```

### 3. Configure environment variables

Create `backend/.env`:
COSMOS_ENDPOINT=https://localhost:8081
COSMOS_KEY=<your-emulator-key>
COSMOS_DATABASE=cogitate
AZURE_STORAGE_CONNECTION_STRING=<your-connection-string>
AZURE_STORAGE_CONTAINER=workbooks
NIM_API_KEY=<your-nvidia-nim-key>
NIM_MODEL=meta/llama-3.1-8b-instruct

### 4. Start CosmosDB Emulator

Download and start the Azure CosmosDB Emulator. Create a database named `cogitate` with three containers:

| Container | Partition Key | TTL |
|---|---|---|
| raters | /engine | Off |
| records | /rater_slug | Off |
| sessions | /upload_id | 7200s |

### 5. Start backend

```bash
cd cogitate-rater-ai-final
uvicorn backend.main:app --reload --port 8000
```

Verify: `http://localhost:8000/health`

### 6. Install frontend dependencies

```bash
cd frontend
npm install
```

### 7. Start frontend

```bash
npm run dev
```

Visit: `http://localhost:3000`

## Engine Selection Guide

| Rater Type | Recommended Engine | Reason |
|---|---|---|
| Simple single-sheet raters | Schema Engine | No `_Schema` sheet required |
| Complex multi-sheet raters | Excel Engine | Preserves full formula chain |
| Actuarial batch models | Excel Engine + Batch Mode | Row-by-row computation |

## Excel Engine Trust Center Setup

For Excel COM to open workbooks programmatically, add the uploads folder as a trusted location:

1. Open Excel → File → Options → Trust Center → Trust Center Settings
2. Trusted Locations → Add new location
3. Path: `<project-root>\backend\uploads\`
4. Check "Subfolders of this location are also trusted"

## API Endpoints
GET  /health
GET  /health/db
POST /api/excel/upload
GET  /api/excel/warm-status/{upload_id}
POST /api/excel/test-calculate
POST /api/excel/save
POST /api/excel/calculate
POST /api/schema/upload
POST /api/schema/calculate
GET  /api/raters/
GET  /api/raters/{slug}/config
POST /api/raters/{slug}/calculate
GET  /api/raters/{slug}/records

## Supported Rater Types

- MPL (Miscellaneous Professional Liability)
- Homeowners (multi-peril)
- Excess D&O / Management Liability (multi-sheet)
- PAR Model (actuarial batch)
- Any custom `.xlsx` workbook