# config.py — Single source of truth for all thresholds and strategies

from pathlib import Path

# ─────────────────────────────────────────────
# CLI DEFAULTS (used by src/cli/cli.py)
# ─────────────────────────────────────────────
DEFAULT_REPORT_PATH = None
DEFAULT_REPORT_DIR = "outputs"
DEFAULT_SAVE_CLEAN = None  # set to a path string to save cleaned CSV by default
DEFAULT_SKIP_CLEAN = False


def project_root() -> Path:
    """Repository root (the directory that contains ``src/``)."""
    return Path(__file__).resolve().parent.parent.parent


def resolve_project_path(path: str) -> str:
    """Resolve a relative path against ``project_root``; absolute paths unchanged."""
    p = Path(path)
    if p.is_absolute():
        return str(p)
    return str(project_root() / p)

# ─────────────────────────────────────────────
# PROFILING
# ─────────────────────────────────────────────
PROFILE_CONFIG = {
    "high_cardinality_threshold": 0.9,   # unique ratio above this = high cardinality
    "low_cardinality_threshold": 0.05,   # unique ratio below this = low cardinality
}

# ─────────────────────────────────────────────
# QUALITY SCORING
# ─────────────────────────────────────────────
QUALITY_CONFIG = {
    "null_warning_threshold": 5.0,       # >5% nulls triggers warning (null_pct is 0–100)
    "null_critical_threshold": 30.0,     # >30% nulls triggers critical flag
    "duplicate_threshold": 0.01,         # >1% duplicates triggers flag
    "constant_column_threshold": 1,      # columns with only 1 unique value
    "high_cardinality_min_unique": 50,   # categorical columns with more unique values → info
    "enable_outlier_checks": True,
    "outlier_iqr_factor": 1.5,
}

SCORE_WEIGHTS = {
    "completeness": 0.40,
    "uniqueness": 0.20,
    "consistency": 0.20,
    "validity": 0.20,
}

# ─────────────────────────────────────────────
# COLUMN FILTERING  (v1.1)
# ─────────────────────────────────────────────
FILTER_CONFIG = {
    # Drop columns where null percentage exceeds this ratio
    "null_drop_threshold": 0.60,

    # Drop columns that have only one unique value (carry no info)
    "drop_single_value_columns": True,

    # Drop columns with only one unique value even if non-null count is high
    "single_value_min_rows": 10,         # only enforce if df has at least this many rows

    # User-specified columns to always drop (populated via CLI or manual override)
    "force_drop_columns": [],
}

# ─────────────────────────────────────────────
# MISSING VALUE HANDLING  (v1.1)
# ─────────────────────────────────────────────
MISSING_VALUE_CONFIG = {
    # Strategy per dtype category: "mean" | "median" | "mode" | "constant" | "drop_rows" | "flag"
    "numeric_strategy": "median",        # median is outlier-robust
    "categorical_strategy": "mode",      # most frequent for strings
    "datetime_strategy": "drop_rows",    # no sensible imputation for dates

    # Constant fill values (used when strategy = "constant")
    "numeric_fill_value": 0,
    "categorical_fill_value": "Unknown",

    # If null ratio in a column exceeds this, skip imputation and flag instead
    # (column should have been dropped by filter step — this is a safety net)
    "impute_max_null_ratio": 0.60,

    # Add a boolean indicator column for imputed values? e.g. "col__was_null"
    "add_null_indicator": False,
}

# ─────────────────────────────────────────────
# TYPE COERCION  (v1.1)
# ─────────────────────────────────────────────
TYPE_COERCION_CONFIG = {
    # Attempt to cast object columns to numeric?
    "coerce_to_numeric": True,

    # Attempt to cast object columns to datetime?
    "coerce_to_datetime": True,

    # Attempt to cast object columns to boolean?
    "coerce_to_bool": True,

    # Recognised boolean string pairs (case-insensitive)
    "bool_true_values": ["true", "yes", "1", "y"],
    "bool_false_values": ["false", "no", "0", "n"],

    # If a column fails numeric cast, what fraction of values must parse
    # successfully before we commit the cast? Avoids partial corruption.
    "numeric_cast_success_threshold": 0.95,

    # Same guard for datetime
    "datetime_cast_success_threshold": 0.90,

    # pandas datetime inference: infer_datetime_format speeds things up
    "datetime_infer_format": True,
}

# ─────────────────────────────────────────────
# REPORTING
# ─────────────────────────────────────────────
REPORT_CONFIG = {
    "max_sample_values": 5,              # max unique values shown in profile
    "show_cleaning_summary": True,       # include cleaning summary section in report
}
