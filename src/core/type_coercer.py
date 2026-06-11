# src/core/type_coercer.py
"""
Type Coercer
------------
Responsibility: Detect and cast columns to their correct dtypes.
                Operates on object-typed columns only — already-typed
                columns are left untouched.

Returns structured data only. No printing. No side effects.
"""

import warnings

import pandas as pd
from typing import Any
from src.config import TYPE_COERCION_CONFIG


def coerce_types(df: pd.DataFrame, config: dict = None) -> dict:
    """
    Entry point. Attempt dtype casting on all object columns.

    Returns:
        {
            "df": pd.DataFrame,           # dataframe with coerced types
            "changes": list[dict],        # one entry per column that changed
            "errors": list[dict],         # columns where coercion was attempted but failed
        }
    """
    cfg = config or TYPE_COERCION_CONFIG
    result_df = df.copy()
    changes = []
    errors = []

    # Include both legacy object dtype and newer pandas StringDtype
    object_cols = result_df.select_dtypes(include=["object", "string"]).columns.tolist()

    for col in object_cols:
        series = result_df[col]

        # Skip columns that are entirely null — nothing to infer
        if series.isna().all():
            continue

        coerced, outcome = _attempt_coercion(series, cfg)

        if outcome["success"]:
            result_df[col] = coerced
            changes.append({
                "column": col,
                "from_dtype": "object",
                "to_dtype": str(coerced.dtype),
                "cast_type": outcome["cast_type"],
                "success_rate": outcome["success_rate"],
            })
        elif outcome["attempted"] and not outcome["success"]:
            errors.append({
                "column": col,
                "attempted_cast": outcome["cast_type"],
                "reason": outcome["reason"],
            })

    return {
        "df": result_df,
        "changes": changes,
        "errors": errors,
    }


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

def _attempt_coercion(series: pd.Series, cfg: dict) -> tuple[pd.Series, dict]:
    """
    Try coercion strategies in priority order: bool → numeric → datetime.
    Returns the first successful cast, or the original series + failure info.
    """

    # 1. Boolean  (must come before numeric — "1"/"0" would pass numeric cast)
    if cfg.get("coerce_to_bool"):
        coerced, outcome = _try_bool(series, cfg)
        if outcome["success"]:
            return coerced, outcome

    # 2. Numeric
    if cfg.get("coerce_to_numeric"):
        coerced, outcome = _try_numeric(series, cfg)
        if outcome["success"]:
            return coerced, outcome

    # 3. Datetime
    if cfg.get("coerce_to_datetime"):
        coerced, outcome = _try_datetime(series, cfg)
        if outcome["success"]:
            return coerced, outcome

    # Nothing worked — return original, no error recorded (just left as object)
    return series, {"attempted": False, "success": False, "cast_type": None, "reason": None, "success_rate": None}


def _try_bool(series: pd.Series, cfg: dict) -> tuple[pd.Series, dict]:
    """Cast if ALL non-null values are recognised bool strings."""
    true_vals  = set(v.lower() for v in cfg.get("bool_true_values", []))
    false_vals = set(v.lower() for v in cfg.get("bool_false_values", []))
    recognised = true_vals | false_vals

    non_null = series.dropna().str.strip().str.lower()

    if non_null.empty or not non_null.isin(recognised).all():
        return series, {"attempted": True, "success": False, "cast_type": "bool",
                        "reason": "Not all values match recognised bool strings", "success_rate": None}

    coerced = series.str.strip().str.lower().map(
        lambda v: True if v in true_vals else (False if v in false_vals else pd.NA)
    ).astype("boolean")

    return coerced, {"attempted": True, "success": True, "cast_type": "bool", "success_rate": 1.0}


def _try_numeric(series: pd.Series, cfg: dict) -> tuple[pd.Series, dict]:
    """Cast to numeric if success rate meets threshold."""
    threshold = cfg.get("numeric_cast_success_threshold", 0.95)

    coerced = pd.to_numeric(series, errors="coerce")
    non_null_original = series.notna().sum()

    if non_null_original == 0:
        return series, {"attempted": True, "success": False, "cast_type": "numeric",
                        "reason": "No non-null values", "success_rate": 0}

    success_rate = coerced.notna().sum() / non_null_original

    if success_rate < threshold:
        return series, {
            "attempted": True, "success": False, "cast_type": "numeric",
            "reason": f"Success rate {success_rate:.2%} below threshold {threshold:.2%}",
            "success_rate": success_rate,
        }

    # Prefer int if no fractional part
    if coerced.dropna().apply(float.is_integer).all():
        coerced = coerced.astype("Int64")   # nullable integer
    
    return coerced, {"attempted": True, "success": True, "cast_type": "numeric", "success_rate": success_rate}


def _try_datetime(series: pd.Series, cfg: dict) -> tuple[pd.Series, dict]:
    """Cast to datetime if success rate meets threshold."""
    threshold = cfg.get("datetime_cast_success_threshold", 0.90)

    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="Could not infer format, so each element will be parsed individually.*",
                category=UserWarning,
            )
            coerced = pd.to_datetime(series, errors="coerce")
    except Exception as e:
        return series, {"attempted": True, "success": False, "cast_type": "datetime",
                        "reason": str(e), "success_rate": None}

    non_null_original = series.notna().sum()
    if non_null_original == 0:
        return series, {"attempted": True, "success": False, "cast_type": "datetime",
                        "reason": "No non-null values", "success_rate": 0}

    success_rate = coerced.notna().sum() / non_null_original

    if success_rate < threshold:
        return series, {
            "attempted": True, "success": False, "cast_type": "datetime",
            "reason": f"Success rate {success_rate:.2%} below threshold {threshold:.2%}",
            "success_rate": success_rate,
        }

    return coerced, {"attempted": True, "success": True, "cast_type": "datetime", "success_rate": success_rate}