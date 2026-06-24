# src/core/deduplicator.py
"""
Deduplicator
------------
Responsibility: Remove duplicate leads from a DataFrame using deterministic,
                explainable rules. No AI, no fuzzy matching, no probabilistic
                merging.

                - Remove exact duplicate rows (all columns identical)
                - Remove email-based duplicates (case-insensitive)
                - Retain the most complete record when duplicates exist
                - Ignore rows with blank emails during email deduplication

Returns structured data only. No printing. No file I/O. No side effects.
"""

import pandas as pd


DEFAULT_DEDUPLICATION_CONFIG = {
    "remove_exact_duplicates": True,
    "remove_email_duplicates": True,
}


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def deduplicate_leads(
    df: pd.DataFrame,
    semantic_profile: dict,
    config: dict | None = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Remove duplicate leads from a DataFrame.

    Args:
        df:                The DataFrame to deduplicate.
        semantic_profile:  Output of ``semantic_profile_dataframe(df)``.
        config:            Optional overrides merged with DEFAULT_DEDUPLICATION_CONFIG.

    Returns:
        (deduplicated_df, deduplication_report)

        deduplicated_df:      DataFrame with duplicates removed.
        deduplication_report:  Dict with counts of removals performed.
    """
    cfg = {**DEFAULT_DEDUPLICATION_CONFIG, **(config or {})}

    input_rows = len(df)
    result_df = df.copy()
    exact_removed = 0
    email_removed = 0

    # ── Step 1: Remove exact duplicate rows ──────────────────────────────
    if cfg["remove_exact_duplicates"]:
        before = len(result_df)
        result_df = result_df.drop_duplicates(keep="first").reset_index(drop=True)
        exact_removed = before - len(result_df)

    # ── Step 2: Remove email-based duplicates ────────────────────────────
    if cfg["remove_email_duplicates"]:
        col_meta = semantic_profile.get("columns", {})
        email_columns = [
            col_name
            for col_name, meta in col_meta.items()
            if meta.get("semantic_type") == "email" and col_name in result_df.columns
        ]

        for col_name in email_columns:
            before = len(result_df)
            result_df = _deduplicate_by_email(result_df, col_name)
            email_removed += before - len(result_df)

    output_rows = len(result_df)

    report = {
        "input_rows": input_rows,
        "output_rows": output_rows,
        "exact_duplicates_removed": exact_removed,
        "email_duplicates_removed": email_removed,
        "rows_retained": output_rows,
    }

    return result_df, report


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

def _deduplicate_by_email(df: pd.DataFrame, email_col: str) -> pd.DataFrame:
    """Remove rows that share the same email address (case-insensitive).

    For each group of duplicates, retain the row with the highest
    completeness score. Rows with blank/missing emails are never
    considered duplicates and are always retained.

    Preserves original row order within the output.
    """
    # Normalize emails for comparison. Blank values get a unique sentinel
    # so they never group together. Use row index as the sentinel key
    # to avoid any shared mutable state.
    normalized = [
        _normalize_email_for_dedup(df[email_col].iloc[i], i)
        for i in range(len(df))
    ]

    # Compute completeness score for every row.
    scores = df.apply(_completeness_score, axis=1)

    # For each group of identical normalized emails, keep the row
    # with the highest completeness score (first occurrence wins ties).
    keep_indices = []
    seen_groups: dict[str, int] = {}  # normalized_email → best_index

    for idx in range(len(df)):
        key = normalized[idx]

        # Blank emails are always kept — they use unique sentinels
        # so each one is its own "group".
        if key not in seen_groups:
            seen_groups[key] = idx
            keep_indices.append(idx)
        else:
            # Compare completeness: if current row is more complete, swap.
            existing_idx = seen_groups[key]
            if scores.iloc[idx] > scores.iloc[existing_idx]:
                # Remove the old winner, add the new one.
                keep_indices.remove(existing_idx)
                keep_indices.append(idx)
                seen_groups[key] = idx
            # else: existing row is better or tied, discard current row.

    # Preserve original ordering.
    keep_indices.sort()
    return df.iloc[keep_indices].reset_index(drop=True)


def _completeness_score(row: pd.Series) -> int:
    """Count the number of non-null, non-empty fields in a row.

    Examples:
        name="John", email="john@example.com"                     → 2
        name="John", email="john@example.com", phone="123", co="" → 3
    """
    score = 0
    for value in row:
        if value is None:
            continue
        if isinstance(value, float) and pd.isna(value):
            continue
        if isinstance(value, str) and value.strip() == "":
            continue
        score += 1
    return score


def _normalize_email_for_dedup(value, row_index: int) -> str:
    """Normalize an email for deduplication comparison.

    - Strips whitespace and lowercases.
    - Blank/None/NaN values return a unique sentinel string (using the
      row index) so they never match each other.

    Args:
        value:     The raw email value from the DataFrame.
        row_index: The positional index of this row, used to generate
                   unique sentinels for blank values.
    """
    if value is None:
        return f"__blank_{row_index}__"
    if isinstance(value, float) and pd.isna(value):
        return f"__blank_{row_index}__"
    s = str(value).strip()
    if s == "":
        return f"__blank_{row_index}__"
    return s.lower()
