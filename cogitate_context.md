# Cogitate Unified Rater Engine — Full Project Context

> **Purpose of this file:** If this conversation ends, paste this entire file into a new session. The assistant will pick up exactly where we left off.

---

## 1. What This Project Is

A unified insurance premium rating engine that consolidates two separately built rater systems (Schema Rater + Excel Rater) into a single product with one UI, one backend, one database, and seamless engine switching under the hood.

The platform accepts Excel-based insurance rater workbooks uploaded by admins, parses them into dynamic forms, and lets clients calculate premiums without ever touching Excel.

---

## 2. The Two Original Systems (Now Being Merged)

### Schema Rater
- **Stack:** React + Vite (frontend), FastAPI port 8000 (backend)
- **Formula engine:** Python `formulas` library (evaluates Excel formulas natively in Python)
- **LLM enrichment:** Was using Gemini API at upload time to auto-enrich field labels/descriptions — Gemini is no longer viable due to API restrictions
- **Flow:** Upload `.xlsx` → auto-parse formula graph → generate schema → serve dynamic form
- **Storage:** Filesystem `/backend/data/raters`
- **Key feature:** No `_Schema` sheet required — it infers fields from the workbook structure

### Excel Rater
- **Stack:** Next.js (frontend), FastAPI port 8001 (backend)
- **Formula engine:** `win32com` — native Excel COM automation (requires Windows + Microsoft Excel installed)
- **Flow:** Upload `.xlsx` with `_Schema` sheet → parse inputs/outputs → 4-step admin review → save → client rates
- **Storage:** Filesystem `/raters`, `/templates`, `/records`
- **Key features:** Downloadable calculated workbook, immutable execution records (`/records`), warm session handling with status polling

### Proxy Gateway (being eliminated)
- Express reverse proxy on port 8080
- Engine selection stored in `cogitate_engine` cookie (`schema` or `excel`)
- Routes frontend + `/api/*` traffic to the selected engine
- **This is being replaced** — no more Express gateway, no more cookie-based switching

---

## 3. Rater Files Analyzed

### MPL Rater for Old Republic v2 (`MPL_Rater_for_Old_Republic_v2_updated.xlsx`)
- **Sheets:** `Rater`, `Application`
- **Type:** Miscellaneous Professional Liability (MPL) insurance
- **Structure:** Inputs in column B (B1–B36), Individual Risk Assessment in column I (I11–I17), outputs in B38–B40, C22–C23, J18
- **Key inputs:** State of Risk, Class Description, Base Rate, Revenue, Longevity, Claims Experience, Risk Management, Subcontracted Work, Retro Date, Deductible, Policy Limit, Split Limit, plus 7 Individual Risk Assessment dropdowns
- **Key outputs:** Total Premium (B40), Final Multiplier (B38), Rating Multiple (C23), Carrier Multiple (C22), Individual Risk (J18), Min Deductible (B25)
- **Notable:** Has state-specific rules (DE, IA, MD, MA, NC, ND, OH) for individual risk min/max caps
- **No `_Schema` sheet** — needs schema engine OR manual `_Schema` added

### template.xlsx
- **Sheets:** `Rater`, `_Schema`, `Application`
- Same rater as MPL Old Republic but with `_Schema` sheet added — this is the Excel engine compatible version
- `_Schema` sheet has columns: `field`, `cell`, `type`, `label`, `direction`, `group`, `options`, `default`
- The `config.json` uploaded is the JSON equivalent of this `_Schema` sheet — proves the config format is already engine-neutral

### PAR Model (`PAR_Model.xlsx`)
- **Sheet:** `Data`
- **Type:** Actuarial life insurance pricing model
- **Structure:** Completely different from MPL — batch computation model with 3000 test cases
- **Inputs per row:** Age, CalcBy (Sum Assured/Premium), Currency (USD/HKD), DB_option, DB_xTPP, DoD_int, mat_age, Prem_freq, Prem_term, PremTarget, Sex, Smoking, SumAssured, BenTerm
- **Outputs per row:** Premium_Rate, AnnualPrem, modal_prem, SA
- **Key distinction:** This is NOT a form-driven single-record rater — it's a batch actuarial computation engine
- **Production note:** PAR Model needs a dedicated "Batch Mode" UI — upload CSV of inputs → download results CSV/Excel — NOT the same single-record form flow as MPL

### Homeowners Rater (`Homeowners_Rater.xlsx`)
- **Sheet:** `Homeowners`
- **Type:** Homeowners insurance excluding earthquake (V1.0.0)
- **Structure:** Complex multi-peril rater — Wind/hail, Wildfire, All other perils calculated separately then summed
- **Key inputs:** Year Built, Building Limit, Coverage Type (Deluxe house/deluxe contents, Condo, Renters), Territory (numbered zones), Deductibles (base, brush/wildfire, wind/hail), 20+ discount/surcharge flags (Burglar alarm, Gated community, Fire resistive, Wildfire suppression, Shelter in place, Roof covering, etc.), Liability coverage limit, optional coverages (Employment practices, Family protection, Workers comp, etc.)
- **Key outputs:** Wind/hail premium, Wildfire premium, All other perils premium, Adjusted Premium, Dollar adjustments, Total premium (~$17,199 in sample)
- **Notable complexity:** Territory-based relativities, peril-specific factor chains, 30+ rating sequence steps
- **No `_Schema` sheet** — best suited for Excel engine (COM) due to formula chain complexity; schema engine would need to trace many interdependent cells

### Excess Follow Form (`Rater_-_Excess_Follow_Form_v2024_1.xlsx`)
- **Sheets:** `XS Rating Step A Inputs`, `XS Rating Step B-F Inputs`, `XS Rating Step G Inputs`, `Endorsement Factors`
- **Type:** Excess Directors & Officers (D&O) / Management Liability insurance
- **Structure:** Multi-sheet rater — each sheet is a rating step (A through G)
- **Key inputs:** State selection, Underlying premium, Underlying limit, Falcon excess limit, Attachment point, Coverage type, Risk factor scores (1–5) for 7 categories (Financial Condition, Nature of Operation, etc.), Side A/IDL coverage, Run-off/ERP options, Schedule rating adjustments (Complexity, Revenue Source, Coverage Enhancements, Primary Coverage Terms), Endorsement selections with rate offset factors
- **Key outputs:** Base premium rate (0.48–0.93 based on risk level), Schedule credit/debit, final premium
- **Notable:** Multi-step sequential calculation across sheets — Step A feeds Step B feeds Step C etc. — strong case for Excel COM engine due to cross-sheet formula dependencies
- **No `_Schema` sheet**

---

## 4. Key Design Decisions Made

### Q: Is this system inclusive to raters like Homeowners and Excess Follow Form?
**Answer: YES.** Here is the breakdown:

| Rater | Engine Recommendation | Reason |
|---|---|---|
| MPL Old Republic | Either (template has `_Schema`) | Simple single-sheet, clean cell mapping |
| Homeowners | Excel COM preferred | 30+ rating steps, territory charts, multi-peril formula chain |
| Excess Follow Form | Excel COM required | Multi-sheet sequential steps (A→G), cross-sheet dependencies |
| PAR Model | Excel COM + Batch Mode | Actuarial batch, not form-driven |

The `_Schema` approach works for simpler single-sheet raters. For complex multi-sheet raters like Homeowners and Excess Follow Form, the Excel COM engine is the right path — it preserves the entire workbook formula chain without needing to map every cell manually.

The system is designed to be **rater-agnostic**: any `.xlsx` workbook can be uploaded. The admin just picks which engine parses it. There is no hardcoded assumption about rater structure beyond what the chosen engine requires.

### Q: What happens if user selects Excel engine but rater has no `_Schema` sheet?

**Decision: Smart fallback with user control — NOT silent auto-switch.**

The flow is:
1. User uploads rater, selects "Excel Engine"
2. Backend checks for `_Schema` sheet
3. If not found → show a clear inline message on the upload screen:

> **"No `_Schema` sheet detected in this workbook."**
> Choose an option:
> - **[Auto-generate Schema]** — We'll scan the workbook and generate a `_Schema` sheet automatically (recommended for simple single-sheet raters)
> - **[Switch to Schema Engine]** — Use the Python formula engine instead (no `_Schema` required)
> - **[Upload `_Schema` manually]** — Download a blank template, fill it in, re-upload

**Why not silent auto-switch?** Because the engines have genuinely different behaviors. Auto-switching without telling the user could produce different premium results silently — unacceptable for insurance calculations. The user must confirm.

The "Auto-generate Schema" option uses the same parsing logic as the Schema Rater's upload pipeline to scan the workbook and produce a `_Schema` sheet, then asks the admin to review it before proceeding with the Excel engine.

---

## 5. The Unified Architecture Plan

### Tech Stack

| Layer | Choice | Replaces |
|---|---|---|
| Frontend | Next.js 14 (App Router) | React+Vite (schema) + Next.js (excel) |
| Backend | Single FastAPI | Two separate FastAPI instances (ports 8000, 8001) |
| Formula Engine A | Python `formulas` | Schema rater engine |
| Formula Engine B | `win32com` Excel COM | Excel rater engine (Windows only) |
| LLM Enrichment | NVIDIA NIM API (OpenAI-compatible, free) | Gemini API (no longer viable) |
| Database | Azure CosmosDB (3 containers) | Filesystem storage |
| File Storage | Azure Blob Storage | Local `/raters`, `/templates`, `/records` dirs |
| Gateway | **Eliminated** | Express reverse proxy on port 8080 |

**No Express proxy. No cookie-based engine switching. No port juggling.**

### Why NVIDIA NIM for LLM?
- Free with NVIDIA Developer Program membership (no credit card, no expiry)
- 80+ models available (Llama, DeepSeek, Mistral, etc.)
- OpenAI-compatible API — swap base URL + API key, zero code change
- ~40 requests/minute rate limit on free tier — fine for upload-time enrichment only
- Used only during schema rater's upload step to auto-enrich field labels/descriptions

---

## 6. CosmosDB Schema Design

### Container 1: `raters` — partition key `/engine`
```json
{
  "id": "uuid",
  "slug": "mpl-old-republic",
  "name": "MPL Old Republic v2",
  "engine": "excel | schema",
  "rater_type": "mpl | par | homeowners | excess | custom",
  "config": { "inputs": [...], "outputs": [...] },
  "meta": { "uploadedAt": "ISO", "uploadedBy": "user_id" },
  "workbook_blob_url": "azure_blob_url",
  "has_schema_sheet": true
}
```

### Container 2: `records` — partition key `/rater_slug`
```json
{
  "id": "uuid",
  "rater_slug": "mpl-old-republic",
  "engine": "excel",
  "inputs": { "state_of_risk": "CO", "revenue": "$3M-$6M", ... },
  "outputs": { "premium": 10007, "final_multiplier": 12.5 },
  "calculated_at": "ISO timestamp",
  "downloaded_workbook_url": "blob_url"
}
```

### Container 3: `sessions` — partition key `/upload_id`
- Transient warm session state during admin upload/review flow
- TTL set to 2 hours — auto-cleanup, no manual purge needed
- Stores parse results, warm status, temp workbook reference

**Rule:** Excel workbooks (`.xlsx` binaries) go to **Azure Blob Storage**, not CosmosDB. CosmosDB stores metadata, config, and records only.

---

## 7. Application Flow

### Splash Screen
Two paths: **Admin Portal** | **Client Panel**
No engine selection at the splash — users don't need to know what engine means.

### Admin Flow
1. Admin lands on persistent dashboard — list of all saved raters (unified, both engines shown with engine badge)
2. Click **Upload Rater** → modal/drawer opens
3. File drop zone + two engine buttons:
   - **"Parse with Schema Engine"** — uses Python `formulas`, no `_Schema` required
   - **"Parse with Excel Engine"** — uses native Excel COM, looks for `_Schema` sheet
4. If Excel engine selected + no `_Schema` found → show the 3-option fallback UI (described in Section 4)
5. Backend parses → returns inputs/outputs mapping for admin review
6. Admin reviews the form preview, can edit field labels if needed
7. **Test Calculate** → see live output
8. **Download calculated workbook** (Excel engine; schema engine shows output values only)
9. **Save** → written to CosmosDB `raters` container + workbook to Blob Storage
10. Rater appears in dashboard with engine badge (subtle pill: "Excel" or "Schema")

### Client Flow (fully engine-agnostic)
1. Client sees rater list (no engine details shown)
2. Pick a rater → dynamic form renders from stored config (same React component regardless of engine)
3. Fill form → **Calculate** → dispatches to correct FastAPI router based on stored `engine` field in CosmosDB
4. Results dashboard displays outputs
5. **Download** option available
6. Execution snapshot written to `records` container

### PAR Model — Batch Mode
- Special toggle in client flow: "Single Record" vs "Batch Mode"
- Batch Mode: upload CSV of inputs → backend runs COM calculation → download results CSV/Excel
- Same UI shell, different form mode, `/api/excel/calculate-batch` endpoint

---

## 8. Backend Structure (Single FastAPI)

```
/api
  /schema
    POST  /upload          # Upload + parse schema (no _Schema sheet needed)
    POST  /calculate       # Calculate with inputs
    POST  /calculate/defaults
    GET   /raters          # List schema-engine raters
    DELETE /raters/{id}

  /excel
    POST  /upload          # Upload + parse _Schema sheet
    GET   /warm-status/{upload_id}
    POST  /test-calculate
    POST  /test-download
    POST  /save
    POST  /calculate       # Calculate with inputs
    POST  /calculate-batch # Batch mode for PAR-type raters
    POST  /calculate-and-download

  /raters                  # UNIFIED endpoints (both engines)
    GET   /                # List all raters (merged from both engines)
    GET   /{slug}/config   # Get rater config
    POST  /{slug}/calculate # Dispatches internally based on engine field
    GET   /{slug}/records  # Get execution history

  /records
    GET   /                # All records
    GET   /{id}

  /health
```

---

## 9. Project Folder Structure

```
cogitate-unified/
├── frontend/                         # Next.js 14 App Router
│   ├── app/
│   │   ├── page.tsx                  # Splash screen
│   │   ├── admin/
│   │   │   ├── page.tsx              # Admin dashboard (rater list)
│   │   │   └── upload/page.tsx      # Upload flow with engine selector
│   │   ├── client/
│   │   │   ├── page.tsx              # Client rater selection
│   │   │   └── [slug]/page.tsx      # Rating form + results
│   │   └── api/                      # Next.js API routes (thin proxy to FastAPI)
│   └── components/
│       ├── RatingForm/               # Shared dynamic form (engine-agnostic)
│       ├── ResultsDashboard/         # Shared results display
│       ├── EngineSelector/           # Two-button upload picker
│       └── NoSchemaFallback/         # Fallback UI when _Schema missing
│
├── backend/                          # Single FastAPI
│   ├── routers/
│   │   ├── schema.py                 # /api/schema/* routes
│   │   ├── excel.py                  # /api/excel/* routes
│   │   └── raters.py                 # /api/raters/* unified endpoints
│   ├── engines/
│   │   ├── schema_engine.py          # Python formulas evaluator
│   │   └── excel_engine.py           # win32com wrapper
│   ├── db/
│   │   ├── cosmos.py                 # CosmosDB client + CRUD helpers
│   │   └── blob.py                   # Azure Blob Storage client
│   ├── services/
│   │   ├── schema_parser.py          # Parses _Schema sheet or infers schema
│   │   ├── nim_enrichment.py         # NVIDIA NIM LLM enrichment at upload time
│   │   └── warm_session.py           # Warm session management (transient)
│   └── models/
│       └── schemas.py                # Pydantic models
│
└── shared/
    └── types/                        # Shared config format (engine-neutral)
```

---

## 10. The `config.json` Format (Engine-Neutral Schema)

This format is used by both engines. It is produced by parsing `_Schema` sheet (Excel engine) or inferred from the workbook (Schema engine). It is stored in CosmosDB and drives the client-side dynamic form regardless of engine.

```json
{
  "slug": "mpl-old-republic",
  "name": "MPL Old Republic v2",
  "sheet": "Rater",
  "inputs": [
    {
      "field": "state_of_risk",
      "cell": "B11",
      "type": "dropdown",
      "label": "State of Risk",
      "group": "Rating Inputs",
      "options": ["AK", "AL", "AR", ...],
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

---

## 11. Features Inherited From Each Engine

| Feature | Source | Included |
|---|---|---|
| Downloadable calculated workbook | Excel Rater | Yes — both engines where possible |
| Immutable execution records | Excel Rater | Yes — CosmosDB `records` container |
| Warm session handling + status polling | Excel Rater | Yes |
| 4-step admin review flow | Excel Rater | Yes — unified UI |
| LLM enrichment at upload time | Schema Rater | Yes — NVIDIA NIM replaces Gemini |
| Startup model preload | Schema Rater | Yes |
| Config-driven dynamic form | Schema Rater | Yes — now used by both engines |
| Batch mode calculation | New | Yes — for PAR-type actuarial raters |
| Engine badge on rater cards | New | Yes — visible to admins, hidden from clients |
| No-schema fallback UI | New | Yes — 3-option flow when _Schema missing |

---

## 12. Prerequisites (unchanged from original)

- **Windows** (required for Excel COM engine / `win32com`)
- Node.js 18+
- Python 3.11+
- Microsoft Excel installed locally (mandatory for Excel Rater COM backend)
- Azure account (CosmosDB + Blob Storage)
- NVIDIA Developer Program account (free — for NIM API key)

---

## 13. Build Order (Recommended)

1. Azure CosmosDB setup — create 3 containers (`raters`, `records`, `sessions`) with partition keys as defined above
2. Azure Blob Storage — create container for workbooks
3. Single FastAPI skeleton — both routers mounted, `/health` endpoint, CosmosDB + Blob clients connected
4. Next.js shell — splash, admin dashboard (rater list from CosmosDB), upload page with engine selector
5. Excel engine integration — COM wrapper, `_Schema` parser, test with MPL template.xlsx
6. Schema engine integration — `formulas` evaluator, test with MPL without `_Schema`
7. Shared `RatingForm` React component — renders from config, works for both engines
8. No-schema fallback UI — the 3-option flow
9. Warm session + status polling
10. Records + download features
11. PAR batch mode (`/api/excel/calculate-batch`)
12. NVIDIA NIM enrichment hook at schema upload time
13. Homeowners + Excess Follow Form rater testing (complex multi-sheet validation)

---

## 14. Rater Compatibility Summary

| Rater | Type | Sheets | Has `_Schema` | Recommended Engine | Special Handling |
|---|---|---|---|---|---|
| MPL Old Republic v2 | Professional Liability | Rater, Application | No | Schema or Excel | None |
| template.xlsx | Professional Liability | Rater, _Schema, Application | Yes | Excel (primary) | None |
| PAR Model | Life Insurance Actuarial | Data | No | Excel COM | Batch Mode UI required |
| Homeowners Rater | Property Insurance | Homeowners | No | Excel COM preferred | Multi-peril, 30+ steps |
| Excess Follow Form | Excess D&O / Mgmt Liability | 4 sheets (Steps A–G + Endorsements) | No | Excel COM required | Multi-sheet sequential steps |
| Any future rater | Any | Any | Optional | Admin chooses | Fallback UI handles missing `_Schema` |

---

## 15. Status At End of Conversation

- [x] Full architecture finalized and agreed upon
- [x] All 5 rater files analyzed and documented
- [x] CosmosDB schema designed
- [x] Both Q&A items answered (inclusivity + no-schema fallback behavior)
- [ ] **Next step: Begin scaffolding** — start with CosmosDB + FastAPI skeleton or Next.js shell (user to confirm which to start with)

---

*Last updated: End of initial planning conversation. Feed this file to a new Claude session and say "continue building the Cogitate Unified Rater from the context file" to resume.*
