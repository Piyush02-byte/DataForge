# src/core/crm_formatter.py
"""
CRM Formatter
-------------
Responsibility: Standardize string-like DataFrame columns for CRM import
                using semantic profile metadata from the Semantic Profiler.

                - Title-case detected name columns (first_name, last_name, full_name)
                - Lowercase detected email columns
                - Strip leading/trailing whitespace from all string columns
                - Split full_name into first_name + last_name columns

Returns structured data only. No printing. No file I/O. No side effects.
"""

import pandas as pd


DEFAULT_CRM_FORMATTER_CONFIG = {
    "split_full_names": True,
    "normalize_emails": True,
    "title_case_names": True,
    "trim_whitespace": True,
}


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def format_for_crm(
    df: pd.DataFrame,
    semantic_profile: dict,
    config: dict | None = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Apply CRM-ready formatting to a DataFrame using semantic column metadata.

    Args:
        df:                The raw DataFrame to format.
        semantic_profile:  Output of ``semantic_profile_dataframe(df)``.
        config:            Optional overrides merged with DEFAULT_CRM_FORMATTER_CONFIG.

    Returns:
        (cleaned_df, report)

        cleaned_df: A copy of the input with formatting transformations applied.
        report:     Dict with counts of actual modifications per transformation.
    """
    cfg = {**DEFAULT_CRM_FORMATTER_CONFIG, **(config or {})}
    result_df = df.copy()
    col_meta = semantic_profile.get("columns", {})

    report = {
        "name_fields_formatted": 0,
        "email_fields_normalized": 0,
        "whitespace_fixes": 0,
        "full_names_split": 0,
    }

    # ── Whitespace cleanup (all string-like columns) ─────────────────────────
    if cfg["trim_whitespace"]:
        report["whitespace_fixes"] = _trim_whitespace(result_df)

    # ── Title-case names ─────────────────────────────────────────────────────
    if cfg["title_case_names"]:
        name_types = {"first_name", "last_name", "full_name"}
        for col_name, meta in col_meta.items():
            if meta.get("semantic_type") in name_types and col_name in result_df.columns:
                report["name_fields_formatted"] += _title_case_column(result_df, col_name)

    # ── Lowercase emails ─────────────────────────────────────────────────────
    if cfg["normalize_emails"]:
        for col_name, meta in col_meta.items():
            if meta.get("semantic_type") == "email" and col_name in result_df.columns:
                report["email_fields_normalized"] += _lowercase_column(result_df, col_name)

    # ── Split full_name → first_name + last_name ─────────────────────────────
    if cfg["split_full_names"]:
        for col_name, meta in col_meta.items():
            if meta.get("semantic_type") == "full_name" and col_name in result_df.columns:
                split_count = _split_full_name(result_df, col_name)
                report["full_names_split"] += split_count

    return result_df, report


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

def _trim_whitespace(df: pd.DataFrame) -> int:
    """Strip leading/trailing whitespace from all object/string columns.

    Returns the total number of individual cell values that were modified.
    """
    fixes = 0
    for col in df.columns:
        if not _is_string_like(df[col]):
            continue

        original = df[col].copy()
        df[col] = df[col].map(
            lambda v: v.strip() if isinstance(v, str) else v
        )
        fixes += int((original != df[col]).sum())

    return fixes


def _title_case_column(df: pd.DataFrame, col_name: str) -> int:
    """Apply title case to a column, preserving hyphens and apostrophes.

    Returns the number of cell values that were modified.
    """
    original = df[col_name].copy()
    df[col_name] = df[col_name].map(
        lambda v: _smart_title_case(v) if isinstance(v, str) else v
    )
    return int((original != df[col_name]).sum())


def _smart_title_case(value: str) -> str:
    """Title-case a name string, correctly handling hyphens and apostrophes.

    Examples:
        "PIYUSH KUMAR"      → "Piyush Kumar"
        "mARY-jANE watson"  → "Mary-Jane Watson"
        "john o'brien"      → "John O'Brien"
    """
    parts = value.split()
    result_tokens = []
    for part in parts:
        # Handle hyphenated names: "mary-jane" → "Mary-Jane"
        if "-" in part:
            sub = "-".join(_capitalize_token(t) for t in part.split("-"))
            result_tokens.append(sub)
        else:
            result_tokens.append(_capitalize_token(part))
    return " ".join(result_tokens)


def _capitalize_token(token: str) -> str:
    """Capitalize a single name token, handling apostrophes.

    "o'brien" → "O'Brien"
    "mcdonald" → "Mcdonald" (MVP — no special prefix handling)
    """
    if "'" in token and len(token) > 2:
        idx = token.index("'")
        return token[: idx + 1].capitalize() + token[idx + 1:].capitalize()
    return token.capitalize()


def _lowercase_column(df: pd.DataFrame, col_name: str) -> int:
    """Lowercase all string values in a column.

    Returns the number of cell values that were modified.
    """
    original = df[col_name].copy()
    df[col_name] = df[col_name].map(
        lambda v: v.lower() if isinstance(v, str) else v
    )
    return int((original != df[col_name]).sum())


def _split_full_name(df: pd.DataFrame, col_name: str) -> int:
    """Split a full_name column into first_name and last_name columns.

    Rules:
        - First token       → first_name
        - Remaining tokens  → last_name (joined with spaces)
        - Original column is preserved (not deleted).
        - If first_name or last_name columns already exist, they are NOT
          overwritten. The split is skipped for safety.

    Returns the number of rows that were successfully split.
    """
    if "first_name" in df.columns or "last_name" in df.columns:
        return 0

    split_count = 0
    first_names = []
    last_names = []

    for value in df[col_name]:
        if not isinstance(value, str) or not value.strip():
            first_names.append(value)
            last_names.append(value)
            continue

        tokens = value.strip().split()
        if len(tokens) >= 2:
            first_names.append(tokens[0])
            last_names.append(" ".join(tokens[1:]))
            split_count += 1
        else:
            first_names.append(tokens[0])
            last_names.append("")
            split_count += 1

    # Insert immediately after the full_name column for logical ordering.
    col_idx = df.columns.get_loc(col_name)
    df.insert(col_idx + 1, "first_name", first_names)
    df.insert(col_idx + 2, "last_name", last_names)

    return split_count


def _is_string_like(series: pd.Series) -> bool:
    return (
        pd.api.types.is_object_dtype(series)
        or pd.api.types.is_string_dtype(series)
    )
