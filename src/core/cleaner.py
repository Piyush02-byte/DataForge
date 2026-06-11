# src/core/cleaner.py
"""
Cleaner
-------
Responsibility: Apply cleaning operations to a DataFrame.
                - filter_columns:        drop columns that fail quality bar
                - handle_missing_values: impute or drop rows with nulls
                - clean:                 orchestrator that runs both in order

Type coercion is handled by type_coercer.py — not this module's concern.
Returns structured data only. No printing. No side effects.
"""

import pandas as pd
from src.config import FILTER_CONFIG, MISSING_VALUE_CONFIG


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def filter_columns(df: pd.DataFrame, config: dict = None) -> dict:
    """
    Drop columns that carry no useful signal.

    Rules (applied in order):
      1. Force-drop any columns listed in config['force_drop_columns']
      2. Drop columns whose null ratio exceeds null_drop_threshold
      3. Drop single-value columns (if enabled and row count >= min threshold)

    Returns:
        {
            "df": pd.DataFrame,
            "dropped_columns": list[dict],   # {column, reason}
            "retained_columns": list[str],
        }
    """
    cfg = config or FILTER_CONFIG
    result_df = df.copy()
    dropped = []

    # Rule 1: force-drop
    force_drop = [c for c in cfg.get("force_drop_columns", []) if c in result_df.columns]
    for col in force_drop:
        dropped.append({"column": col, "reason": "force_drop"})
    result_df = result_df.drop(columns=force_drop, errors="ignore")

    # Rule 2: null threshold
    null_threshold = cfg.get("null_drop_threshold", 0.60)
    null_ratios = result_df.isnull().mean()
    null_drop_cols = null_ratios[null_ratios > null_threshold].index.tolist()
    for col in null_drop_cols:
        dropped.append({
            "column": col,
            "reason": f"null_ratio {null_ratios[col]:.1%} exceeds threshold {null_threshold:.1%}",
        })
    result_df = result_df.drop(columns=null_drop_cols, errors="ignore")

    # Rule 3: single-value columns
    if cfg.get("drop_single_value_columns", True):
        min_rows = cfg.get("single_value_min_rows", 10)
        if len(result_df) >= min_rows:
            for col in result_df.columns:
                if result_df[col].nunique(dropna=True) <= 1:
                    dropped.append({"column": col, "reason": "single_unique_value"})
            single_val_cols = [d["column"] for d in dropped if d["reason"] == "single_unique_value"]
            result_df = result_df.drop(columns=single_val_cols, errors="ignore")

    return {
        "df": result_df,
        "dropped_columns": dropped,
        "retained_columns": result_df.columns.tolist(),
    }


def handle_missing_values(df: pd.DataFrame, config: dict = None) -> dict:
    """
    Impute or drop rows with missing values based on config strategy.

    Strategies per dtype:
      numeric:     mean | median | constant | drop_rows | flag
      categorical: mode | constant | drop_rows | flag
      datetime:    drop_rows | flag

    Returns:
        {
            "df": pd.DataFrame,
            "actions": list[dict],     # one entry per column touched
            "rows_dropped": int,
        }
    """
    cfg = config or MISSING_VALUE_CONFIG
    result_df = df.copy()
    actions = []
    rows_before = len(result_df)

    numeric_cols   = result_df.select_dtypes(include="number").columns.tolist()
    datetime_cols  = result_df.select_dtypes(include="datetime").columns.tolist()
    # Everything else is treated as categorical (object, bool, etc.)
    categorical_cols = [
        c for c in result_df.columns
        if c not in numeric_cols and c not in datetime_cols
    ]

    # Safety net: skip columns above impute threshold (filter step should have caught these)
    impute_max = cfg.get("impute_max_null_ratio", 0.60)

    def _should_skip(col):
        ratio = result_df[col].isnull().mean()
        return ratio > impute_max

    # --- Numeric ---
    num_strategy = cfg.get("numeric_strategy", "median")
    for col in numeric_cols:
        if result_df[col].isnull().sum() == 0:
            continue
        if _should_skip(col):
            actions.append({"column": col, "action": "skipped", "reason": "null_ratio_too_high"})
            continue

        result_df, action = _apply_numeric_strategy(result_df, col, num_strategy, cfg)
        actions.append(action)

    # --- Categorical ---
    cat_strategy = cfg.get("categorical_strategy", "mode")
    for col in categorical_cols:
        if result_df[col].isnull().sum() == 0:
            continue
        if _should_skip(col):
            actions.append({"column": col, "action": "skipped", "reason": "null_ratio_too_high"})
            continue

        result_df, action = _apply_categorical_strategy(result_df, col, cat_strategy, cfg)
        actions.append(action)

    # --- Datetime ---
    dt_strategy = cfg.get("datetime_strategy", "drop_rows")
    for col in datetime_cols:
        if result_df[col].isnull().sum() == 0:
            continue

        if dt_strategy == "drop_rows":
            before = len(result_df)
            result_df = result_df.dropna(subset=[col])
            actions.append({"column": col, "action": "drop_rows", "rows_removed": before - len(result_df)})
        elif dt_strategy == "flag":
            indicator_col = f"{col}__was_null"
            result_df[indicator_col] = result_df[col].isnull()
            actions.append({"column": col, "action": "flagged", "indicator_column": indicator_col})

    rows_after = len(result_df)

    return {
        "df": result_df,
        "actions": actions,
        "rows_dropped": rows_before - rows_after,
    }


def clean(df: pd.DataFrame, filter_config: dict = None, missing_config: dict = None) -> dict:
    """
    Orchestrator: run filter → handle missing values in correct order.
    Type coercion is a separate step handled by pipeline.py via type_coercer.py.

    Returns:
        {
            "df": pd.DataFrame,
            "filter_result": dict,
            "missing_result": dict,
        }
    """
    filter_result  = filter_columns(df, config=filter_config)
    missing_result = handle_missing_values(filter_result["df"], config=missing_config)

    return {
        "df": missing_result["df"],
        "filter_result": filter_result,
        "missing_result": missing_result,
    }


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

def _apply_numeric_strategy(
    df: pd.DataFrame, col: str, strategy: str, cfg: dict
) -> tuple[pd.DataFrame, dict]:
    null_count = df[col].isnull().sum()

    if strategy == "mean":
        fill_val = df[col].mean()
        df[col] = df[col].fillna(fill_val)
        return df, {"column": col, "action": "filled_mean", "fill_value": round(fill_val, 4), "nulls_filled": null_count}

    elif strategy == "median":
        fill_val = df[col].median()
        df[col] = df[col].fillna(fill_val)
        return df, {"column": col, "action": "filled_median", "fill_value": round(fill_val, 4), "nulls_filled": null_count}

    elif strategy == "constant":
        fill_val = cfg.get("numeric_fill_value", 0)
        df[col] = df[col].fillna(fill_val)
        return df, {"column": col, "action": "filled_constant", "fill_value": fill_val, "nulls_filled": null_count}

    elif strategy == "drop_rows":
        before = len(df)
        df = df.dropna(subset=[col])
        return df, {"column": col, "action": "drop_rows", "rows_removed": before - len(df)}

    elif strategy == "flag":
        indicator_col = f"{col}__was_null"
        df[indicator_col] = df[col].isnull()
        return df, {"column": col, "action": "flagged", "indicator_column": indicator_col}

    return df, {"column": col, "action": "no_action", "reason": f"unknown strategy: {strategy}"}


def _apply_categorical_strategy(
    df: pd.DataFrame, col: str, strategy: str, cfg: dict
) -> tuple[pd.DataFrame, dict]:
    null_count = df[col].isnull().sum()

    if strategy == "mode":
        mode_vals = df[col].mode()
        if mode_vals.empty:
            return df, {"column": col, "action": "no_action", "reason": "mode undefined (all null)"}
        fill_val = mode_vals[0]
        df[col] = df[col].fillna(fill_val)
        return df, {"column": col, "action": "filled_mode", "fill_value": fill_val, "nulls_filled": null_count}

    elif strategy == "constant":
        fill_val = cfg.get("categorical_fill_value", "Unknown")
        df[col] = df[col].fillna(fill_val)
        return df, {"column": col, "action": "filled_constant", "fill_value": fill_val, "nulls_filled": null_count}

    elif strategy == "drop_rows":
        before = len(df)
        df = df.dropna(subset=[col])
        return df, {"column": col, "action": "drop_rows", "rows_removed": before - len(df)}

    elif strategy == "flag":
        indicator_col = f"{col}__was_null"
        df[indicator_col] = df[col].isnull()
        return df, {"column": col, "action": "flagged", "indicator_column": indicator_col}

    return df, {"column": col, "action": "no_action", "reason": f"unknown strategy: {strategy}"}
