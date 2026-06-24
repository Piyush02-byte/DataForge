"""
Semantic Profiler
-----------------
Responsibility: Detect real-world semantic meaning for string-like DataFrame
                columns by inspecting cell values and lightweight header hints.

Returns structured data only. No printing. No file I/O. No side effects.
"""

import re
from typing import Callable

import pandas as pd


DEFAULT_SEMANTIC_CONFIG = {
    "sample_size": 100,
    "min_non_null_for_detection": 3,
    "confidence_threshold": 0.60,
    "header_boost": 0.20,
}

HEADER_ALIASES = {
    "email": ["email", "e-mail", "email_address", "emailaddress", "mail"],
    "phone_number": ["phone", "mobile", "tel", "telephone", "phone_number", "contact_number"],
    "first_name": ["first_name", "firstname", "first", "fname", "given_name"],
    "last_name": ["last_name", "lastname", "last", "lname", "surname", "family_name"],
    "full_name": ["name", "full_name", "fullname", "contact_name", "person"],
    "company_name": ["company", "company_name", "organization", "organisation", "org", "employer", "firm"],
    "url": ["url", "website", "web", "link", "homepage", "site"],
    "linkedin_profile": ["linkedin", "linkedin_url", "linkedin_profile"],
}

COMPANY_SUFFIXES = [
    "llc",
    "inc",
    "ltd",
    "corp",
    "gmbh",
    "pvt",
    "llp",
    "co.",
    "plc",
    "s.a.",
    "ag",
    "pte",
    "limited",
    "incorporated",
    "corporation",
    "pvt ltd",
    "pvt. ltd.",
    "private limited",
]

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
NAME_TOKEN_RE = re.compile(r"^[A-Za-z]+(?:[-'][A-Za-z]+)*$")


def semantic_profile_dataframe(df: pd.DataFrame, config: dict | None = None) -> dict:
    """
    Detect semantic column types for object/string columns in a DataFrame.

    Returns:
        {
            "columns": {column_name: semantic_result},
            "detected_types_summary": {semantic_type: [column_names]},
        }
    """
    cfg = {**DEFAULT_SEMANTIC_CONFIG, **(config or {})}

    columns = {}
    summary = {}

    for col in df.columns:
        result = _profile_column(col, df[col], cfg)
        columns[col] = result
        summary.setdefault(result["semantic_type"], []).append(col)

    return {
        "columns": columns,
        "detected_types_summary": summary,
    }


# ─────────────────────────────────────────────
# Detector functions
# ─────────────────────────────────────────────

def _is_email(value: str) -> bool:
    return bool(EMAIL_RE.match(value.strip()))


def _is_phone_number(value: str) -> bool:
    stripped = value.strip()
    if not stripped or not (stripped[0].isdigit() or stripped[0] == "+"):
        return False

    cleaned = re.sub(r"[+\-().\s]", "", stripped)
    return cleaned.isdigit() and 7 <= len(cleaned) <= 15


def _is_url(value: str) -> bool:
    lower = value.strip().lower()
    if lower.startswith(("http://", "https://")):
        remainder = lower.split("://", 1)[1]
        return "." in remainder
    if lower.startswith("www."):
        return "." in lower[4:]
    return False


def _is_linkedin_profile(value: str) -> bool:
    lower = value.strip().lower()
    return _is_url(lower) and "linkedin.com" in lower


def _is_full_name(value: str) -> bool:
    stripped = value.strip()
    if not 3 <= len(stripped) <= 60:
        return False
    if _is_company_name(stripped):
        return False

    tokens = stripped.split()
    return 2 <= len(tokens) <= 4 and all(NAME_TOKEN_RE.match(token) for token in tokens)


def _is_single_name_token(value: str) -> bool:
    stripped = value.strip()
    return 2 <= len(stripped) <= 20 and bool(NAME_TOKEN_RE.match(stripped))


def _is_company_name(value: str) -> bool:
    """Detect company names by known legal suffixes."""
    lower = value.strip().lower()
    return any(lower.endswith(suffix) for suffix in COMPANY_SUFFIXES)


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

def _profile_column(column_name: str, series: pd.Series, cfg: dict) -> dict:
    if not _is_string_like(series):
        return _unknown_result(
            reason=f"column dtype is {series.dtype}; skipped semantic detection",
            header_matched=False,
        )

    values = _sample_values(series, cfg)
    min_required = cfg["min_non_null_for_detection"]

    if len(values) < min_required:
        return _unknown_result(
            reason=f"only {len(values)} non-null values; below minimum threshold of {min_required}",
            header_matched=False,
            sample_size=len(values),
        )

    candidates = _candidate_detectors(column_name)
    threshold = cfg["confidence_threshold"]

    # Step 1: Score every detector for this column.
    scored_results = []
    for priority_index, (semantic_type, detector) in enumerate(candidates):
        match_count = sum(1 for value in values if detector(value))
        match_ratio = match_count / len(values)
        header_matched = _header_matches(column_name, semantic_type)
        confidence = min(1.0, match_ratio + (cfg["header_boost"] if header_matched else 0.0))

        scored_results.append({
            "semantic_type": semantic_type,
            "confidence": round(confidence, 2),
            "reason": _match_reason(match_count, len(values), semantic_type, header_matched),
            "header_matched": header_matched,
            "sample_size": len(values),
            "match_count": match_count,
            "detector": "regex_v1",
            "_priority_index": priority_index,
        })

    # Step 2: Filter to candidates that exceed the threshold.
    above_threshold = [r for r in scored_results if r["confidence"] >= threshold]

    if above_threshold:
        # Pick the candidate with the highest confidence.
        # If tied, the candidate with the lower priority index wins (tiebreaker).
        winner = max(above_threshold, key=lambda r: (r["confidence"], -r["_priority_index"]))
        # Remove internal field before returning.
        winner.pop("_priority_index", None)
        return winner

    # No detector passed — return unknown.
    # Use the highest-scoring detector's metadata for context.
    best = max(scored_results, key=lambda r: (r["confidence"], -r["_priority_index"]))
    header_matched = any(_header_matches(column_name, semantic_type) for semantic_type, _ in candidates)
    return _unknown_result(
        reason=f"no detector exceeded confidence threshold of {threshold:.2f}",
        header_matched=header_matched,
        sample_size=len(values),
        match_count=best["match_count"],
        confidence=best["confidence"],
    )


def _candidate_detectors(column_name: str) -> list[tuple[str, Callable[[str], bool]]]:
    if _header_matches(column_name, "last_name"):
        single_name_type = "last_name"
    else:
        single_name_type = "first_name"

    return [
        ("linkedin_profile", _is_linkedin_profile),
        ("email", _is_email),
        ("phone_number", _is_phone_number),
        ("url", _is_url),
        ("full_name", _is_full_name),
        (single_name_type, _is_single_name_token),
        ("company_name", _is_company_name),
    ]


def _is_string_like(series: pd.Series) -> bool:
    return (
        pd.api.types.is_object_dtype(series)
        or pd.api.types.is_string_dtype(series)
    )


def _sample_values(series: pd.Series, cfg: dict) -> list[str]:
    cleaned = series.dropna().map(lambda value: str(value).strip())
    cleaned = cleaned[cleaned != ""]

    sample_size = min(len(cleaned), cfg["sample_size"])
    if sample_size == 0:
        return []

    sampled = cleaned.sample(n=sample_size, random_state=42)
    return sampled.tolist()


def _header_matches(column_name: str, semantic_type: str) -> bool:
    normalized = str(column_name).strip().lower().replace(" ", "_")
    return normalized in HEADER_ALIASES.get(semantic_type, [])


def _match_reason(match_count: int, sample_size: int, semantic_type: str, header_matched: bool) -> str:
    reason = f"{match_count}/{sample_size} sampled values matched {semantic_type} pattern"
    if header_matched:
        reason += "; header boost applied"
    return reason


def _unknown_result(
    *,
    reason: str,
    header_matched: bool,
    sample_size: int = 0,
    match_count: int = 0,
    confidence: float = 0.0,
) -> dict:
    return {
        "semantic_type": "unknown",
        "confidence": round(confidence, 2),
        "reason": reason,
        "header_matched": header_matched,
        "sample_size": sample_size,
        "match_count": match_count,
        "detector": "none",
    }
