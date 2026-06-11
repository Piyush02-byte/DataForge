# src/core/pipeline.py
"""
Pipeline
--------
Responsibility: Orchestrate the full data quality and preprocessing flow.
                Owns the execution order. Never contains business logic.

Flow:
    load → profile → quality checks → quality score → suggestions
        → filter_columns → handle_missing_values → coerce_types → report

Returns a structured result dict. Always includes 'success' and 'error' keys.
CLI receives this dict — never raw exceptions.
"""

import os
import traceback
from datetime import datetime

import pandas as pd

from src.core.loader           import load_csv
from src.core.profiler         import profile_dataframe
from src.core.quality          import run_quality_checks, quality_summary
from src.core.quality_scorer   import compute_quality_score
from src.core.suggestions_engine import generate_suggestions
from src.core.cleaner          import clean
from src.core.type_coercer     import coerce_types
from src.core.reporter         import generate_report, write_html_report
from src.utils.config          import DEFAULT_REPORT_DIR, DEFAULT_REPORT_PATH, resolve_project_path
from src.config import (
    FILTER_CONFIG,
    MISSING_VALUE_CONFIG,
    TYPE_COERCION_CONFIG,
    REPORT_CONFIG,
)


def _clean_actions_log(clean_result: dict) -> list:
    """Human-readable lines for CLI from structured clean_result."""
    lines = []
    for d in clean_result.get("filter_result", {}).get("dropped_columns", []):
        col = d.get("column", "?")
        reason = d.get("reason", "")
        lines.append(f"Dropped column '{col}': {reason}")
    for a in clean_result.get("missing_result", {}).get("actions", []):
        col = a.get("column", "?")
        act = a.get("action", "")
        lines.append(f"{col}: {act}")
    return lines


def _resolve_report_path(output_path: str | None) -> str:
    """Resolve explicit report paths or create a timestamped default path."""
    if output_path:
        return resolve_project_path(output_path)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"dataforge_report_{timestamp}.html"
    return resolve_project_path(os.path.join(DEFAULT_REPORT_DIR, filename))


def run_pipeline(
    filepath: str,
    options: dict = None,
    *,
    output_path: str | None = None,
    skip_clean: bool = False,
    save_clean: str | None = None,
) -> dict:
    """
    Execute the full pipeline on a CSV file.

    Args:
        filepath: Path to the CSV file.
        options:  Optional overrides for any config section.
                  Keys: "filter", "missing", "coercion", "report"
        output_path: HTML report path. If omitted, a timestamped report is
                     generated under the default output directory.
        skip_clean: If True, skip filter + missing-value cleaning (coercion still runs).
        save_clean: If set, write the final DataFrame to this CSV path.

    Returns:
        Dict with CLI fields (meta, profile, issues, clean_df, report_path) plus
        stages and summary for programmatic use.
    """
    opts = options or {}
    stages = {}
    # Relative paths are anchored to the repo root (not the process cwd), so
    # generated reports and explicit output paths always live under the project
    # folder unless an absolute output path is provided.
    report_file = _resolve_report_path(output_path or DEFAULT_REPORT_PATH)

    try:
        # ── 1. Load ──────────────────────────────────────────────────────────
        load_result = load_csv(filepath)
        stages["load"] = load_result

        if not load_result.get("success"):
            return _failure(load_result.get("error", "Load failed"), stages)

        df: pd.DataFrame = load_result["df"]
        meta = load_result.get("meta", {})

        # ── 2. Profile ───────────────────────────────────────────────────────
        profile_result = profile_dataframe(df)
        stages["profile"] = profile_result

        # ── 3. Quality Checks ────────────────────────────────────────────────
        quality_result = run_quality_checks(df, profile_result)
        stages["quality"] = quality_result

        # ── 4. Quality Score ─────────────────────────────────────────────────
        score_result = compute_quality_score(df)
        stages["score"] = score_result

        # ── 5. Suggestions ───────────────────────────────────────────────────
        suggestions_result = generate_suggestions(df)
        stages["suggestions"] = suggestions_result

        # ── 6. Filter Columns ────────────────────────────────────────────────
        filter_cfg  = opts.get("filter", FILTER_CONFIG)
        missing_cfg = opts.get("missing", MISSING_VALUE_CONFIG)

        if skip_clean:
            clean_result = {
                "df": df.copy(),
                "filter_result": {
                    "dropped_columns": [],
                    "retained_columns": df.columns.tolist(),
                },
                "missing_result": {"actions": [], "rows_dropped": 0},
            }
        else:
            clean_result = clean(df, filter_config=filter_cfg, missing_config=missing_cfg)
        stages["clean"] = clean_result

        cleaned_df: pd.DataFrame = clean_result["df"]

        # ── 7. Type Coercion ─────────────────────────────────────────────────
        coercion_cfg = opts.get("coercion", TYPE_COERCION_CONFIG)
        coercion_result = coerce_types(cleaned_df, config=coercion_cfg)
        stages["coercion"] = coercion_result

        final_df: pd.DataFrame = coercion_result["df"]

        # ── 8. Report ────────────────────────────────────────────────────────
        report_cfg = opts.get("report", REPORT_CONFIG)
        report_result = generate_report(
            df_original    = df,
            df_cleaned     = final_df,
            profile        = profile_result,
            quality        = quality_result,
            score          = score_result,
            suggestions    = suggestions_result,
            clean          = clean_result,
            coercion       = coercion_result,
            config         = report_cfg,
        )
        stages["report"] = report_result

        write_html_report(
            report_result,
            report_file,
            os.path.basename(filepath),
        )
        if save_clean:
            final_df.to_csv(resolve_project_path(save_clean), index=False)

        # ── Summary for CLI ──────────────────────────────────────────────────
        summary = _build_summary(df, final_df, score_result, clean_result, coercion_result)
        clean_log = _clean_actions_log(clean_result)

        return {
            "success":         True,
            "error":           None,
            "meta":            meta,
            "profile":         profile_result,
            "issues":          quality_result,
            "quality_summary": quality_summary(quality_result),
            "clean_log":       clean_log,
            "report_path":     os.path.abspath(report_file),
            "clean_df":        final_df,
            "stages":          stages,
            "summary":         summary,
        }

    except Exception as exc:
        return _failure(
            error=f"{type(exc).__name__}: {exc}",
            stages=stages,
            tb=traceback.format_exc(),
        )


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

def _build_summary(
    df_original: pd.DataFrame,
    df_cleaned: pd.DataFrame,
    score_result: dict,
    clean_result: dict,
    coercion_result: dict,
) -> dict:
    filter_res  = clean_result.get("filter_result", {})
    missing_res = clean_result.get("missing_result", {})

    return {
        "rows_original":     len(df_original),
        "rows_final":        len(df_cleaned),
        "rows_dropped":      missing_res.get("rows_dropped", 0),
        "cols_original":     len(df_original.columns),
        "cols_final":        len(df_cleaned.columns),
        "cols_dropped":      len(filter_res.get("dropped_columns", [])),
        "cols_type_cast":    len(coercion_result.get("changes", [])),
        "quality_score":     score_result.get("score"),
        "quality_grade":     score_result.get("grade"),
    }


def _failure(error: str, stages: dict, tb: str = None) -> dict:
    return {
        "success": False,
        "error":   error,
        "stages":  stages,
        "summary": {},
        "traceback": tb,
    }
