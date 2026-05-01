from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# ── Routers ───────────────────────────────────────────────────
from routers import schema, excel, raters

app = FastAPI(
    title="Cogitate Unified Rater API",
    description="Unified insurance premium rating engine — Schema + Excel COM engines",
    version="1.0.0"
)

# ── CORS ──────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Route registration ────────────────────────────────────────
app.include_router(schema.router,  prefix="/api/schema",  tags=["Schema Engine"])
app.include_router(excel.router,   prefix="/api/excel",   tags=["Excel Engine"])
app.include_router(raters.router,  prefix="/api/raters",  tags=["Raters (Unified)"])

# ── Health check ──────────────────────────────────────────────
@app.get("/health", tags=["Health"])
def health():
    return {
        "status": "ok",
        "engines": ["schema", "excel"],
        "version": "1.0.0"
    }

# ── CosmosDB connection test ──────────────────────────────────
@app.get("/health/db", tags=["Health"])
def health_db():
    try:
        from db.cosmos import raters_container, records_container, sessions_container
        raters_container.read()
        records_container.read()
        sessions_container.read()
        return {
            "status": "ok",
            "cosmos": "connected",
            "containers": ["raters", "records", "sessions"]
        }
    except Exception as e:
        return {
            "status": "error",
            "cosmos": "failed",
            "detail": str(e)
        }

# ── Entry point ───────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)