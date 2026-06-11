import pandas as pd

# =============================================================================
# quality_scorer.py — Single source of truth for dataset quality scoring.
#
# Rule: ONE formula. ONE place. Reporter, pipeline, API all import from here.
#       Never redefine quality logic anywhere else in the codebase.
#
# Score formula:
#   Start at 100.
#   Penalize missing values   → up to -40 points (weighted by severity)
#   Penalize duplicates        → up to -20 points
#   Penalize constant columns  → -5 per column (dead weight in a dataset)
#   Penalize outlier columns   → -3 per column
#   Floor: 0. Score never goes negative.
# =============================================================================


# ── Thresholds (aligned with config) ─────────────────────────────────────────
# These mirror src/utils/config.py — do not redefine there.

STATUS_EXCELLENT : int = 85
STATUS_GOOD      : int = 70
STATUS_MODERATE  : int = 50
# Below 50 → POOR


# ── Penalty Functions ─────────────────────────────────────────────────────────

def _missing_penalty(df: pd.DataFrame) -> float:
    """
    Penalize based on % of total cells that are missing.
    Scaled 0–40: even 10% missing is a serious data quality problem.
    """
    total_cells = df.shape[0] * df.shape[1]
    if total_cells == 0:
        return 0.0

    missing_pct = (df.isnull().sum().sum() / total_cells) * 100
    return min(missing_pct * 0.4, 40.0)


def _duplicate_penalty(df: pd.DataFrame) -> float:
    """
    Penalize based on % of rows that are duplicates.
    Scaled 0–20.
    """
    if len(df) == 0:
        return 0.0

    dup_pct = (df.duplicated().sum() / len(df)) * 100
    return min(dup_pct * 0.2, 20.0)


def _constant_column_penalty(df: pd.DataFrame) -> float:
    """
    Each column with only 1 unique value carries -5 points.
    A constant column is dead weight — it provides zero information.
    """
    constant_count = sum(1 for col in df.columns if df[col].nunique() <= 1)
    return min(constant_count * 5.0, 20.0)


def _outlier_penalty(df: pd.DataFrame) -> float:
    """
    Each numeric column with IQR-detected outliers carries -3 points.
    Outliers skew models and aggregations silently — they deserve a penalty.
    """
    penalty = 0.0

    for col in df.select_dtypes(include="number").columns:
        series = df[col].dropna()
        if len(series) < 4:
            continue

        Q1  = series.quantile(0.25)
        Q3  = series.quantile(0.75)
        IQR = Q3 - Q1

        outliers = ((series < Q1 - 1.5 * IQR) | (series > Q3 + 1.5 * IQR)).sum()
        if outliers > 0:
            penalty += 3.0

    return min(penalty, 15.0)


# ── Main Scorer ───────────────────────────────────────────────────────────────

def calculate_quality_score(df: pd.DataFrame) -> float:
    """
    Returns a quality score from 0–100.
    Higher is better. 100 means a perfectly clean dataset.

    Used by: pipeline.py, reporter.py, (future) FastAPI response.
    """
    if df is None or df.empty:
        return 0.0

    score = 100.0
    score -= _missing_penalty(df)
    score -= _duplicate_penalty(df)
    score -= _constant_column_penalty(df)
    score -= _outlier_penalty(df)

    return round(max(score, 0.0), 2)


def compute_quality_score(df: pd.DataFrame) -> dict:
    """
    Pipeline entry point: wraps ``calculate_quality_score`` with grade metadata.

    Returns:
        {"score": float, "grade": str, "breakdown": dict}
    """
    score = float(calculate_quality_score(df))
    return {
        "score":     score,
        "grade":     quality_status(score),
        "breakdown": {},
    }


def quality_status(score: float) -> str:
    """
    Maps a numeric score to a human-readable status label.
    Used in reports, API responses, and CLI output.
    """
    if score >= STATUS_EXCELLENT:
        return "Excellent"
    if score >= STATUS_GOOD:
        return "Good"
    if score >= STATUS_MODERATE:
        return "Moderate"
    return "Poor"


def score_color(score: float) -> str:
    """
    Returns a hex color for UI rendering based on score.
    Used by reporter.py — single source for score color logic.
    """
    if score >= STATUS_EXCELLENT:
        return "#1e8449"   # green
    if score >= STATUS_GOOD:
        return "#d68910"   # amber
    if score >= STATUS_MODERATE:
        return "#e67e22"   # orange
    return "#c0392b"       # red