# server.py
"""
DataForge Lead List Scrubber — FastAPI Backend
----------------------------------------------
Thin API wrapper around the DataForge processing pipeline (INT-001).

Endpoints:
    GET  /         — Serve frontend
    GET  /health   — Health check
    POST /process  — Upload CSV, receive ZIP with results

No authentication. No database. No sessions. No disk writes.
"""

import io
import json
import zipfile
import traceback
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from src.core.pipeline import process_lead_list


# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────

MAX_UPLOAD_SIZE_MB = 25
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
SUPPORTED_EXTENSIONS = [".csv"]


# ─────────────────────────────────────────────
# App
# ─────────────────────────────────────────────

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="DataForge Lead List Scrubber",
    description="Upload a messy lead list CSV. Receive a CRM-ready CSV in seconds.",
    version="0.1.0",
)

# CORS — allow the frontend to call the API from any origin during dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static assets (CSS, JS) at /static/*
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def serve_frontend():
    """Serve the single-page frontend."""
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/process")
async def process_csv(file: UploadFile = File(...)):
    """
    Upload a CSV lead list and receive a ZIP with processed results.

    Returns a ZIP containing:
        - crm_ready.csv       — CRM-formatted, validated, deduplicated leads
        - rejected_leads.csv  — Leads that failed validation with reasons
        - report.json         — Processing report with counts from each stage
    """
    # ── Validate file presence ───────────────────────────────────────────
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    # ── Validate file extension ──────────────────────────────────────────
    filename = file.filename.lower()
    if not any(filename.endswith(ext) for ext in SUPPORTED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported",
        )

    # ── Read file contents ───────────────────────────────────────────────
    try:
        contents = await file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to read uploaded file")

    # ── Validate file size ───────────────────────────────────────────────
    if len(contents) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum size of {MAX_UPLOAD_SIZE_MB}MB",
        )

    # ── Parse CSV ────────────────────────────────────────────────────────
    try:
        df = pd.read_csv(io.BytesIO(contents))
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to parse CSV file")

    # ── Validate non-empty ───────────────────────────────────────────────
    if len(df) == 0:
        raise HTTPException(status_code=400, detail="CSV contains no rows")

    # ── Process ──────────────────────────────────────────────────────────
    try:
        result = process_lead_list(df)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        # Log internally but never expose tracebacks to the client.
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Processing failed")

    # ── Package results ──────────────────────────────────────────────────
    zip_buffer = _create_results_zip(
        crm_ready_df=result["crm_ready_df"],
        rejected_df=result["rejected_df"],
        report=result["report"],
    )

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=dataforge_results.zip",
        },
    )


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _create_results_zip(
    crm_ready_df: pd.DataFrame,
    rejected_df: pd.DataFrame,
    report: dict,
) -> io.BytesIO:
    """Create an in-memory ZIP containing the processing results.

    Contents:
        crm_ready.csv       — The cleaned, CRM-ready leads
        rejected_leads.csv  — Leads that failed validation
        report.json         — Processing statistics

    No files are written to disk.
    """
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # crm_ready.csv
        crm_csv = crm_ready_df.to_csv(index=False)
        zf.writestr("crm_ready.csv", crm_csv)

        # rejected_leads.csv
        rejected_csv = rejected_df.to_csv(index=False)
        zf.writestr("rejected_leads.csv", rejected_csv)

        # report.json
        report_json = json.dumps(report, indent=2, default=str)
        zf.writestr("report.json", report_json)

    zip_buffer.seek(0)
    return zip_buffer
