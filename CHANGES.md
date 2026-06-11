# Summary of changes (csv-data-quality-pipeline)

This document lists edits made to align the CLI, pipeline, config, reporting, and quality checks. Paths are relative to the project root: `C:\Users\piyus\csv-data-quality-pipeline`.

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
