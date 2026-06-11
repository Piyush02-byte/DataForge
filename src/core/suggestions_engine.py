import pandas as pd
from typing import List, Dict, Any

# =============================================================================
# suggestions_engine.py — Actionable, column-specific data quality suggestions.
#
# Rule: Every suggestion must answer three questions:
#   1. What is the problem?
#   2. Which column / scope?
#   3. What should the engineer do about it?
#
# Output is structured dicts — not flat strings.
# Reason: CLI can print them. Reporter can render them. API can return them.
#         Flat strings can only be printed. Structured data can do anything.
#
# Schema per suggestion:
#   {
#       "type"    : str   — machine-readable category
#       "severity": str   — "high" | "medium" | "low"
#       "scope"   : str   — column name or "dataset"
#       "message" : str   — human-readable problem description
#       "action"  : str   — concrete fix the engineer should apply
#   }
# =============================================================================


def _suggest_missing(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Column-level missing value suggestions with fill strategy hints."""

    suggestions = []

    for col in df.columns:
        null_pct = df[col].isnull().mean() * 100
        if null_pct == 0:
            continue

        # Determine fill strategy based on column type
        if pd.api.types.is_numeric_dtype(df[col]):
            action = f"Fill with median (skewed) or mean (normal). Current missing: {null_pct:.1f}%."
        else:
            mode = df[col].mode()
            mode_val = f'"{mode[0]}"' if len(mode) > 0 else "unknown"
            action = f"Fill with mode ({mode_val}) or constant 'unknown'. Current missing: {null_pct:.1f}%."

        severity = "high" if null_pct > 40 else ("medium" if null_pct > 10 else "low")

        suggestions.append({
            "type"    : "missing_values",
            "severity": severity,
            "scope"   : col,
            "message" : f"'{col}' has {null_pct:.1f}% missing values.",
            "action"  : action
        })

    return suggestions


def _suggest_duplicates(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Dataset-level duplicate row suggestion."""

    dup_count = df.duplicated().sum()
    if dup_count == 0:
        return []

    dup_pct = (dup_count / len(df)) * 100

    return [{
        "type"    : "duplicates",
        "severity": "high" if dup_pct > 10 else "medium",
        "scope"   : "dataset",
        "message" : f"{dup_count} duplicate rows detected ({dup_pct:.1f}% of dataset).",
        "action"  : "Call df.drop_duplicates(keep='first') before analysis or modeling."
    }]


def _suggest_constant_columns(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Flag columns with zero variance — they add no information."""

    suggestions = []

    for col in df.columns:
        if df[col].nunique() <= 1:
            suggestions.append({
                "type"    : "constant_column",
                "severity": "medium",
                "scope"   : col,
                "message" : f"'{col}' has only 1 unique value — zero information content.",
                "action"  : f"Drop this column: df.drop(columns=['{col}'])."
            })

    return suggestions


def _suggest_outliers(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """IQR-based outlier detection with capping suggestion."""

    suggestions = []

    for col in df.select_dtypes(include="number").columns:
        series = df[col].dropna()
        if len(series) < 4:
            continue

        Q1  = series.quantile(0.25)
        Q3  = series.quantile(0.75)
        IQR = Q3 - Q1

        lower = Q1 - 1.5 * IQR
        upper = Q3 + 1.5 * IQR

        outlier_count = int(((series < lower) | (series > upper)).sum())

        if outlier_count > 0:
            suggestions.append({
                "type"    : "outliers",
                "severity": "medium",
                "scope"   : col,
                "message" : f"'{col}' has {outlier_count} outliers outside IQR bounds [{lower:.2f}, {upper:.2f}].",
                "action"  : f"Cap with: df['{col}'] = df['{col}'].clip({lower:.2f}, {upper:.2f})."
            })

    return suggestions


def _suggest_type_conversion(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Only flag object columns where 80%+ of values are actually numeric.
    Not every string column needs conversion — only the obvious ones.
    """

    suggestions = []

    for col in df.select_dtypes(include="object").columns:
        non_null = df[col].dropna()
        if len(non_null) == 0:
            continue

        converted = pd.to_numeric(non_null, errors="coerce")
        success_rate = converted.notna().sum() / len(non_null)

        if success_rate >= 0.8:
            suggestions.append({
                "type"    : "type_conversion",
                "severity": "low",
                "scope"   : col,
                "message" : f"'{col}' is stored as object but {success_rate*100:.0f}% of values are numeric.",
                "action"  : f"Convert with: df['{col}'] = pd.to_numeric(df['{col}'], errors='coerce')."
            })

    return suggestions


def _suggest_high_cardinality(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Flag categorical columns with too many unique values.
    High cardinality = one-hot encoding explosion in ML pipelines.
    """

    suggestions = []

    for col in df.select_dtypes(include="object").columns:
        unique_count = df[col].nunique()
        total        = len(df[col].dropna())

        if total == 0:
            continue

        unique_ratio = unique_count / total

        if unique_count > 50 and unique_ratio < 0.9:
            suggestions.append({
                "type"    : "high_cardinality",
                "severity": "low",
                "scope"   : col,
                "message" : f"'{col}' has {unique_count} unique values — high cardinality.",
                "action"  : "Consider target encoding, frequency encoding, or grouping rare categories."
            })

    return suggestions


# ── Main Entry ────────────────────────────────────────────────────────────────

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def generate_suggestions(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Returns a prioritized list of actionable suggestions for the dataset.

    Sorted by severity: high → medium → low.
    Each suggestion is a structured dict — renderable by CLI, HTML report,
    or JSON API without transformation.
    """
    if df is None or df.empty:
        return []

    suggestions = []
    suggestions += _suggest_missing(df)
    suggestions += _suggest_duplicates(df)
    suggestions += _suggest_constant_columns(df)
    suggestions += _suggest_outliers(df)
    suggestions += _suggest_type_conversion(df)
    suggestions += _suggest_high_cardinality(df)

    # Sort high → medium → low
    suggestions.sort(key=lambda s: SEVERITY_ORDER.get(s["severity"], 99))

    return suggestions
