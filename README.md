# DataForge

![Python](https://img.shields.io/badge/Python-3.13-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.137-009688)
![Status](https://img.shields.io/badge/Status-Active-green)
![Version](https://img.shields.io/badge/Version-v0.1.0-orange)
![Tests](https://img.shields.io/badge/Tests-179%20passing-brightgreen)
![License](https://img.shields.io/badge/License-MIT-yellow)

> Upload a messy lead list. Download a CRM-ready file.

DataForge is a self-hosted lead list cleaning tool. It takes a raw CSV of leads — with messy names, invalid emails, duplicates, and inconsistent formatting — and produces a CRM-ready dataset in seconds.

No AI. No external APIs. No accounts. Fully deterministic and explainable.

**[Live Demo →](https://dataforge-kcvd.onrender.com)** · **[API Docs →](https://dataforge-kcvd.onrender.com/docs)**

---

## Tech Stack

| Layer | Technology |
|:---|:---|
| Backend | Python 3.13 · FastAPI · Uvicorn |
| Frontend | Vanilla HTML · CSS · JavaScript |
| Processing | Pandas · Regex-based NLP |
| Testing | Pytest (179 tests) |
| Deployment | Render (Web Service) |

---

## What It Does

| Step | Module | What Happens |
|:---|:---|:---|
| 1 | Semantic Recognition | Auto-detects column types: email, name, phone, company, URL, LinkedIn |
| 2 | CRM Formatting | Title-cases names, lowercases emails, trims whitespace, splits full names |
| 3 | Email Validation | Rejects invalid emails, flags role-based addresses (info@, sales@) |
| 4 | Deduplication | Removes exact and email-based duplicates, keeps the most complete record |

**Output:** A ZIP containing three files:

| File | Contents |
|:---|:---|
| `crm_ready.csv` | Cleaned, validated, deduplicated leads |
| `rejected_leads.csv` | Invalid leads with rejection reasons |
| `report.json` | Processing statistics from every stage |

---

## Architecture

```text
                    Browser (localhost:8000)
                           │
                    ┌──────┴──────┐
                    │  Frontend   │  static/index.html
                    │  (Vanilla)  │  static/style.css
                    │             │  static/app.js
                    └──────┬──────┘
                           │ POST /process (multipart CSV)
                           ▼
                    ┌──────────────┐
                    │   FastAPI    │  server.py
                    │   Backend   │
                    └──────┬──────┘
                           │
                           ▼
              ┌────────────────────────┐
              │   Processing Pipeline  │  src/core/pipeline.py
              └────────────┬───────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   ┌─────────────┐ ┌─────────────┐ ┌──────────────┐
   │  Semantic   │ │    CRM      │ │    Email     │
   │  Profiler   │ │  Formatter  │ │  Validator   │
   │  DF-001     │ │  DF-002     │ │  DF-003      │
   └─────────────┘ └─────────────┘ └──────────────┘
                                          │
                                          ▼
                                   ┌──────────────┐
                                   │ Deduplicator │
                                   │   DF-004     │
                                   └──────┬───────┘
                                          │
                                          ▼
                                    ZIP Response
                                   (3 CSV/JSON files)
```

**Pipeline flow:**

```text
Input CSV → Semantic Recognition → CRM Formatting → Re-profile
         → Email Validation (split: valid + rejected)
         → Deduplication (on valid only) → ZIP package → Response
```

---

## Quick Start

Clone the repository:

```bash
git clone https://github.com/Piyush02-byte/DataForge.git
cd DataForge
```

Create and activate a virtual environment:

```bash
python -m venv venv
```

On Windows:

```powershell
.\venv\Scripts\Activate.ps1
```

On macOS or Linux:

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the server:

```bash
uvicorn server:app --reload
```

Open your browser:

```
http://localhost:8000
```

Drop a CSV → click **Process Lead List** → download the ZIP.

---

## Deployment (Render)

DataForge deploys as a Render Web Service with zero configuration files needed.

| Setting | Value |
|:---|:---|
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn server:app --host 0.0.0.0 --port $PORT` |
| **Runtime** | Python 3 |
| **Plan** | Free |

No environment variables, no database, no Docker required.

See the [Render deployment guide](https://render.com/docs/deploy-fastapi) for step-by-step instructions.

---

## API Reference

### GET /health

Health check. Used by Render for automatic health monitoring.

```bash
curl https://dataforge-kcvd.onrender.com/health
```

```json
{"status": "ok"}
```

### POST /process

Upload a CSV and receive a ZIP with processed results.

```bash
curl -X POST https://dataforge-kcvd.onrender.com/process \
  -F "file=@leads.csv" \
  -o dataforge_results.zip
```

**Responses:**

| Code | Condition |
|:---|:---|
| 200 | Success — returns ZIP |
| 400 | No file / wrong extension / empty CSV / parse failure |
| 500 | Processing failure |

### GET /docs

Interactive Swagger UI (auto-generated by FastAPI).

---

## Python API

Use the engine directly without the web server:

```python
import pandas as pd
from src.core import process_lead_list

df = pd.read_csv("leads.csv")
result = process_lead_list(df)

crm_ready = result["crm_ready_df"]      # Cleaned leads
rejected  = result["rejected_df"]        # Invalid leads with reasons
report    = result["report"]             # Processing statistics
```

Individual modules can also be used standalone:

```python
from src.core import (
    semantic_profile_dataframe,  # DF-001
    format_for_crm,              # DF-002
    validate_leads,              # DF-003
    deduplicate_leads,           # DF-004
)
```

---

## Design Principles

- **Deterministic** — Same input always produces the same output
- **Explainable** — Every rejection and detection includes a reason
- **No AI / No LLMs** — Pure regex and rule-based logic
- **No external APIs** — Runs entirely offline, no SMTP/DNS lookups
- **Safe** — No data loss; rejected rows are preserved with reasons
- **No disk writes** — All processing happens in memory

---

## Project Structure

```text
DataForge/
├── server.py                      FastAPI backend (WEB-001)
├── static/
│   ├── index.html                 Single-page frontend (WEB-002)
│   ├── style.css                  Dark-mode design system
│   └── app.js                     Upload, ZIP parsing, download logic
├── src/
│   ├── core/
│   │   ├── __init__.py            Public API exports
│   │   ├── semantic_profiler.py   DF-001: Column type detection
│   │   ├── crm_formatter.py       DF-002: CRM formatting engine
│   │   ├── validators.py          DF-003: Email validation engine
│   │   ├── deduplicator.py        DF-004: Deduplication engine
│   │   ├── pipeline.py            INT-001: Processing orchestrator
│   │   ├── loader.py              CSV loading
│   │   ├── profiler.py            Column profiling
│   │   ├── quality.py             Quality checks
│   │   ├── quality_scorer.py      Quality scoring
│   │   ├── cleaner.py             Data cleaning
│   │   ├── suggestions_engine.py  Fix suggestions
│   │   ├── type_coercer.py        Type coercion
│   │   └── reporter.py            HTML report generator
│   ├── cli/                       CLI interface (maincsv.py)
│   ├── pipeline/                  Legacy orchestration
│   ├── utils/                     Config and exceptions
│   └── config.py                  Configuration re-exports
├── tests/
│   ├── test_semantic_profiler.py  25 tests
│   ├── test_crm_formatter.py      31 tests
│   ├── test_validators.py         39 tests
│   ├── test_deduplicator.py       32 tests
│   ├── test_pipeline.py           29 tests
│   └── test_api.py                23 tests
├── codex/                         Technical design documents
├── data/
│   └── sample.csv                 Sample dataset
├── docs/                          Documentation assets
├── maincsv.py                     Legacy CLI entry point
├── requirements.txt               Python dependencies
├── CHANGES.md                     Changelog
└── README.md
```

---

## Test Coverage

```bash
python -m pytest tests/ -v
```

| Suite | Tests | Coverage |
|:---|:---:|:---|
| DF-001 Semantic Profiler | 25 | Type detection, confidence, edge cases |
| DF-002 CRM Formatter | 31 | Title case, email normalization, name splitting |
| DF-003 Email Validator | 39 | Regex validation, blank/role detection, config |
| DF-004 Deduplicator | 32 | Exact/email dedup, completeness scoring |
| INT-001 Pipeline | 29 | End-to-end flow, config overrides, edge cases |
| WEB-001 FastAPI API | 23 | Endpoints, error handling, ZIP contents |
| **Total** | **179** | |

---

## Configuration

The pipeline accepts optional config dicts to control behavior:

```python
result = process_lead_list(df, config={
    "run_formatting": True,       # Enable/disable CRM formatting
    "run_validation": True,       # Enable/disable email validation
    "run_deduplication": True,    # Enable/disable deduplication
})
```

Server constants in `server.py`:

```python
MAX_UPLOAD_SIZE_MB = 25
SUPPORTED_EXTENSIONS = [".csv"]
```

---

## Known Limitations

- **Minimum 3 rows required** for semantic type detection. Datasets with 1–2 rows pass through unmodified.
- **No fuzzy matching** in deduplication. Only exact and email-based dedup.
- **No SMTP/DNS validation** of email addresses. Validation is regex-based.
- **Synchronous processing.** Large files block the request thread.
- **No authentication.** Intended for local/trusted network use.

---

## Roadmap

- [ ] Upload progress bar for large files
- [ ] In-browser preview of cleaned data before download
- [ ] Configurable validation rules via UI
- [ ] Batch processing (multiple CSVs)
- [ ] Export to Google Sheets / HubSpot format
- [ ] Docker image for one-command deployment
- [ ] CI/CD pipeline with automated testing

---

## Legacy CSV Audit Tool

The original `maincsv.py` CLI tool for CSV profiling and quality auditing remains in the codebase. To use it:

```bash
python maincsv.py data/sample.csv
```

This generates an HTML audit report at `outputs/report.html`. See [CHANGES.md](CHANGES.md) for the history of that tool.

---

## Contributing

Contributions are welcome. Before opening a pull request:

1. Run the full test suite: `python -m pytest tests/ -v`
2. Verify the server starts: `uvicorn server:app --reload`
3. Test a CSV upload through the browser at `http://localhost:8000`

---

## License

MIT
