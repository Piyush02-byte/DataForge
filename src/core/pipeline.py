# src/core/pipeline.py
"""
Lead List Processing Pipeline
------------------------------
Responsibility: Orchestrate the full lead-list cleaning flow by calling the
                four MVP modules in sequence:

                1. Semantic Recognition   (DF-001)
                2. CRM Formatting         (DF-002)
                3. Email Validation        (DF-003)
                4. Smart Deduplication     (DF-004)

                Returns a CRM-ready DataFrame, a rejected-leads DataFrame,
                and a combined processing report.

Returns structured data only. No printing. No file I/O. No side effects.
"""

import pandas as pd

from src.core.semantic_profiler import semantic_profile_dataframe
from src.core.crm_formatter import format_for_crm
from src.core.validators import validate_leads
from src.core.deduplicator import deduplicate_leads


DEFAULT_PIPELINE_CONFIG = {
    "run_formatting": True,
    "run_validation": True,
    "run_deduplication": True,
}


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def process_lead_list(
    df: pd.DataFrame,
    config: dict | None = None,
) -> dict:
    """
    Process a raw lead list through the full DataForge pipeline.

    Args:
        df:     The raw DataFrame (typically loaded from a CSV).
        config: Optional overrides merged with DEFAULT_PIPELINE_CONFIG.
                May also include sub-configs keyed by module name:
                ``"formatting_config"``, ``"validation_config"``,
                ``"deduplication_config"``.

    Returns:
        {
            "crm_ready_df": pd.DataFrame,
            "rejected_df":  pd.DataFrame,
            "report":       dict,
        }

    Raises:
        ValueError: If the input DataFrame is empty.
        TypeError:  If the input is not a pandas DataFrame.
    """
    # ── Input validation ─────────────────────────────────────────────────
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected a pandas DataFrame, got {type(df).__name__}")

    if len(df) == 0:
        raise ValueError("Input DataFrame is empty")

    cfg = {**DEFAULT_PIPELINE_CONFIG, **(config or {})}
    input_rows = len(df)
    working_df = df.copy()

    # ── Step 1: Semantic Recognition (always runs) ───────────────────────
    semantic_profile = semantic_profile_dataframe(working_df)
    semantic_types_detected = len([
        t for t in semantic_profile.get("detected_types_summary", {})
        if t != "unknown"
    ])

    # ── Step 2: CRM Formatting ───────────────────────────────────────────
    formatting_report = {}
    if cfg["run_formatting"]:
        formatting_config = cfg.get("formatting_config")
        working_df, formatting_report = format_for_crm(
            working_df, semantic_profile, config=formatting_config,
        )
        # Re-run semantic profiling after formatting since columns may have
        # changed (e.g., full_name split into first_name + last_name).
        semantic_profile = semantic_profile_dataframe(working_df)

    # ── Step 3: Email Validation ─────────────────────────────────────────
    rejected_df = pd.DataFrame()
    validation_report = {}
    if cfg["run_validation"]:
        validation_config = cfg.get("validation_config")
        working_df, rejected_df, validation_report = validate_leads(
            working_df, semantic_profile, config=validation_config,
        )

    # ── Step 4: Deduplication ────────────────────────────────────────────
    deduplication_report = {}
    if cfg["run_deduplication"]:
        deduplication_config = cfg.get("deduplication_config")
        working_df, deduplication_report = deduplicate_leads(
            working_df, semantic_profile, config=deduplication_config,
        )

    # ── Step 5: Report Assembly ──────────────────────────────────────────
    report = {
        "input_rows": input_rows,
        "output_rows": len(working_df),
        "rejected_rows": len(rejected_df),
        "semantic_types_detected": semantic_types_detected,
        "crm_formatting": formatting_report,
        "validation": validation_report,
        "deduplication": deduplication_report,
    }

    return {
        "crm_ready_df": working_df,
        "rejected_df": rejected_df,
        "report": report,
    }
