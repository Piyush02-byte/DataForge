import pandas as pd
from src.config import QUALITY_CONFIG
from src.utils.exceptions import QualityCheckError


def _check_missing(df, profile):

    issues = []

    for col, info in profile.items():

        pct = info["null_pct"]

        if pct > QUALITY_CONFIG["null_critical_threshold"]:
            issues.append({
                "column"  : col,
                "check"   : "missing_values",
                "severity": "critical",
                "message" : f"{pct:.1f}% values missing",
                "affected": info["null_count"]
            })

        elif pct > QUALITY_CONFIG["null_warning_threshold"]:
            issues.append({
                "column"  : col,
                "check"   : "missing_values",
                "severity": "warning",
                "message" : f"{pct:.1f}% values missing",
                "affected": info["null_count"]
            })

    return issues


def _check_duplicates(df):

    dup = df.duplicated().sum()

    if dup > 0:
        return [{
            "column"  : "all columns",
            "check"   : "duplicates",
            "severity": "warning",
            "message" : f"{dup} duplicate rows",
            "affected": int(dup)
        }]

    return []


def _check_constant(profile):

    issues = []

    for col, info in profile.items():

        if info["unique"] <= 1:
            issues.append({
                "column"  : col,
                "check"   : "constant_column",
                "severity": "warning",
                "message" : "Column has only 1 unique value — no information",
                "affected": info["total"]
            })

    return issues


def _check_high_cardinality(profile):

    issues = []

    for col, info in profile.items():

        if (
            info["inferred_type"] == "categorical"
            and info["unique"] > QUALITY_CONFIG["high_cardinality_min_unique"]
        ):
            issues.append({
                "column"  : col,
                "check"   : "high_cardinality",
                "severity": "info",
                "message" : f"{info['unique']} unique values in categorical column",
                "affected": info["unique"]
            })

    return issues


def _check_outliers(df, profile):
    """IQR-based outlier detection for numeric columns."""

    if not QUALITY_CONFIG.get("enable_outlier_checks", True):
        return []

    issues = []
    iqr_factor = float(QUALITY_CONFIG.get("outlier_iqr_factor", 1.5))

    for col, info in profile.items():

        if info["inferred_type"] != "numeric":
            continue

        series = df[col].dropna()

        Q1  = series.quantile(0.25)
        Q3  = series.quantile(0.75)
        IQR = Q3 - Q1

        lower = Q1 - iqr_factor * IQR
        upper = Q3 + iqr_factor * IQR

        outlier_count = int(((series < lower) | (series > upper)).sum())

        if outlier_count > 0:
            issues.append({
                "column"  : col,
                "check"   : "outliers",
                "severity": "warning",
                "message" : f"{outlier_count} outliers detected (IQR method)",
                "affected": outlier_count
            })

    return issues


def run_quality_checks(df, profile):

    try:
        issues = []
        issues += _check_missing(df, profile)
        issues += _check_duplicates(df)
        issues += _check_constant(profile)
        issues += _check_high_cardinality(profile)
        issues += _check_outliers(df, profile)
        return issues

    except Exception as e:
        raise QualityCheckError("run_quality_checks", str(e))


def quality_summary(issues):

    summary = {
        "critical": 0,
        "warning": 0,
        "info": 0,
        "total": len(issues)
    }

    for issue in issues:

        severity = issue.get("severity","info")

        if severity == "critical":
            summary["critical"] += 1

        elif severity == "warning":
            summary["warning"] += 1

        elif severity == "info":
            summary["info"] += 1

    return summary
