# Changelog

---

## v0.1.0 — Lead List Scrubber MVP (2026-06-20)

First release. Transforms raw CSV lead lists into CRM-ready datasets through a four-stage processing pipeline with a web interface.

### New Modules

#### DF-001: Semantic Recognition (`src/core/semantic_profiler.py`)

- Auto-detects column types: email, phone_number, full_name, first_name, last_name, company_name, url, linkedin_profile
- Evaluate-all-then-pick-highest scoring architecture (v1.2)
- Confidence-based selection with priority tiebreaking
- Minimum 3 non-null values threshold to prevent false positives
- Explainability: every detection includes `confidence`, `detector`, and `reason` fields
- Header-name boosting for ambiguous columns

#### DF-002: CRM Formatter (`src/core/crm_formatter.py`)

- Title Case normalization for name fields
- Lowercase normalization for email fields
- Whitespace trimming across all detected fields
- Full name splitting: "John Smith" → first_name: "John", last_name: "Smith"
- Transformation report with per-field counts

#### DF-003: Email Validator (`src/core/validators.py`)

- Regex-based email format validation
- Blank/None/NaN email rejection
- Role-based email flagging (info@, sales@, support@, etc.)
- Per-row rejection reasons (`INVALID_EMAIL_FORMAT`, `BLANK_EMAIL`)
- Splits DataFrame into valid and rejected sets
- Configurable: disable blank rejection, role flagging, or strict validation

#### DF-004: Smart Deduplicator (`src/core/deduplicator.py`)

- Exact row deduplication (all columns identical)
- Email-based deduplication (case-insensitive)
- Completeness scoring: retains the row with the most non-null fields
- Blank emails never grouped as duplicates (unique sentinels)
- Stateless design: no global counters, safe for concurrent server requests

#### INT-001: Processing Pipeline (`src/core/pipeline.py`)

- Orchestrates all four modules in sequence
- Re-profiles after CRM formatting (name splitting changes schema)
- Each step independently toggleable via config
- Strict input validation: empty DataFrame raises ValueError, non-DataFrame raises TypeError
- Unified report combining sub-reports from every stage

#### WEB-001: FastAPI Backend (`server.py`)

- `GET /health` — Health check
- `POST /process` — CSV upload → ZIP response (multipart/form-data)
- `GET /` — Serve frontend
- `GET /docs` — Swagger UI
- In-memory ZIP generation via BytesIO (no disk writes)
- CORS middleware for frontend dev
- File size limit: 25MB
- Error responses: 400 (client errors), 500 (processing failures), no tracebacks exposed

#### WEB-002: Single-Page Frontend (`static/`)

- Drag-and-drop CSV upload with visual feedback
- Client-side file validation (extension, size)
- Processing spinner with status text
- In-browser ZIP parsing to extract report.json for stats display
- Animated counters (Rows Processed / Rejected / Retained)
- Download trigger for dataforge_results.zip
- Dark-mode design system with Inter typography
- Responsive layout (mobile-friendly)
- SVG favicon

### QA & Fixes

- QA audit: 88 end-to-end test scenarios, all passing
- Fixed global `_blank_counter` state leak in deduplicator (M2)
- Added missing dependencies to requirements.txt (L3)
- Added favicon to frontend (L1)

### Documentation

- Complete README.md rewrite for Lead List Scrubber
- Updated architecture diagram and project structure
- Fixed requirements.txt version drift (pinned to tested runtime versions)
- Scoped .gitignore rules to never exclude static/ frontend files
- Updated CHANGES.md with full module history

### Test Coverage

- 179 automated tests across 7 test files
- All tests passing on Python 3.13, pandas 2.3.3, FastAPI 0.137.1

---

## Legacy Pipeline Changes

The following changes were made to the original CSV audit/profiling pipeline prior to the Lead List Scrubber work.

---

## 1. `src/pipeline/pipeline.py`

- **Imports:** Fixed `suggestions_engine` import spacing; added `quality_summary`, `write_html_report`, `DEFAULT_REPORT_PATH`, `resolve_project_path`.
- **`run_pipeline` signature:** Added keyword arguments `output_path`, `skip_clean`, `save_clean` so `maincsv.py` / `cli.py` can call it without `TypeError`.
- **Loader contract:** Expects `load_csv` to return a dict with `success`, `df`, `meta`, `error` (not a raw tuple).
- **Cleaning:** `skip_clean=True` skips `clean()` and uses an identity clean result; coercion still runs.
- **Reporting:** Calls `write_html_report` after `generate_report`; optional `save_clean` writes the final CSV.
- **Return value:** On success, returns CLI-friendly keys: `meta`, `profile`, `issues`, `quality_summary`, `clean_log`, `report_path`, `clean_df`, plus `stages` and `summary`.
- **`_clean_actions_log`:** Builds human-readable lines for the CLI from filter + missing-value results.
- **Scoring / suggestions:** Uses `compute_quality_score(df)` and `generate_suggestions(df)` (DataFrame-based APIs).
- **Paths:** Report and `save_clean` paths go through `resolve_project_path` so relative paths are under the **repo root**, not the shell’s current directory.

---

## 2. `src/core/loader.py`

- **`load_csv` return value:** Returns a single dict: `success`, `df`, `meta`, `error` (with try/except on failure) instead of `(df, meta)` only.

---

## 3. `src/core/quality.py`

- **Thresholds:** Replaced undefined `MISSING_WARNING_THRESHOLD` / `MISSING_CRITICAL_THRESHOLD` with `QUALITY_CONFIG["null_warning_threshold"]` and `QUALITY_CONFIG["null_critical_threshold"]`.
- **Outliers / cardinality:** Replaced undefined `ENABLE_OUTLIER_CAPPING`, `OUTLIER_IQR_FACTOR`, and `HIGH_CARDINALITY_THRESHOLD` with entries from `QUALITY_CONFIG`.
- **Imports:** Removed unused `numpy` and `profile_dataframe`.

---

## 4. `src/utils/config.py`

- **`QUALITY_CONFIG`:** `null_*` thresholds set to **5.0** and **30.0** to match profiler `null_pct` on a **0–100** scale (not 0–1).
- **CLI defaults:** `DEFAULT_REPORT_PATH`, `DEFAULT_SAVE_CLEAN`, `DEFAULT_SKIP_CLEAN`.
- **Default report file:** `DEFAULT_REPORT_PATH = "outputs/report.html"`.
- **Extra quality keys:** e.g. `high_cardinality_min_unique`, `enable_outlier_checks`, `outlier_iqr_factor`.
- **`project_root()` / `resolve_project_path()`:** Moved here (replacing a short-lived `src/utils/paths.py` module) so outputs resolve relative to the repository root.

---

## 5. `src/config.py` (new)

- Re-exports settings from `src.utils.config` so `from src.config import …` works for `FILTER_CONFIG`, `QUALITY_CONFIG`, etc.

---

## 6. `src/core/quality_scorer.py`

- **`compute_quality_score(df)`:** New wrapper returning `{"score", "grade", "breakdown"}` for the pipeline/reporter; internally uses `calculate_quality_score` and `quality_status`.

---

## 7. `src/core/reporter.py`

- **`generate_report` inputs:** `_build_issues_section` and `_build_suggestions_section` accept either a **list** or the older dict shape.
- **`write_html_report`:** Replaced a JSON-in-`<pre>` dump with a **structured HTML report** (overview, score, profiles table, issues, suggestions, cleaning, coercion).
- **Helpers:** `_h`, `_table`, `_section`, and section renderers for HTML; removed dependency on `json` for the main report output.

---

## 8. `src/utils/exceptions.py`

- **Renamed** custom `FileNotFoundError` to **`CSVFileNotFoundError`** so it does not shadow Python’s built-in `FileNotFoundError`.

---

## 9. `src/cli/cli.py`

- **Imports:** `resolve_project_path` from `src.utils.config`; removed unused `CSVAnalyzerError`.
- **`validate_args`:** Creates output (and save-clean) directories using **resolved** project paths.
- **`_print_summary`:** Prints `result["report_path"]` when present so the user sees the **absolute** report location.

---

## 10. Removed / cleaned up

- **`src/utils/paths.py`:** Added briefly, then **removed**; logic lives in `src/utils/config.py`.
- **Accidental `path\` folder** at project root (e.g. from `--output path/to/report.html`): **deleted**; not required by the application.

---

## Files not heavily changed here

- `maincsv.py` — still entry point; `sys.path` + `cli.main()`.
- `src/core/cleaner.py`, `type_coercer.py`, `profiler.py`, `suggestions_engine.py` — used as-is aside from pipeline wiring.
- `backup_v1/` — legacy; not wired into the current CLI.

---

## How to run

From the project root (or any cwd — outputs still land under this repo):

```text
python maincsv.py data/sample.csv
```

Default HTML report: **`outputs/report.html`** (under this repository).
