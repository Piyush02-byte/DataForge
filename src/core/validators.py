# src/core/validators.py
"""
Validators
----------
Responsibility: Validate semantic email columns and classify DataFrame rows
                into valid leads and rejected leads.

                - Validate email format using deterministic regex
                - Reject blank/missing emails
                - Reject malformed domains
                - Reject whitespace-containing emails
                - Flag role-based emails (info@, sales@, etc.) without rejecting
                - Track rejection reasons per row

Returns structured data only. No printing. No file I/O. No side effects.
No external APIs. No SMTP. No DNS. No third-party services.
"""

import re

import pandas as pd


DEFAULT_VALIDATOR_CONFIG = {
    "reject_blank_emails": True,
    "flag_role_accounts": True,
    "strict_email_validation": True,
}

EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)

ROLE_PREFIXES = [
    "info",
    "sales",
    "support",
    "admin",
    "contact",
    "hello",
    "team",
    "billing",
    "help",
    "noreply",
    "no-reply",
    "postmaster",
    "webmaster",
    "abuse",
]


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def validate_leads(
    df: pd.DataFrame,
    semantic_profile: dict,
    config: dict | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Validate email columns and split the DataFrame into valid and rejected leads.

    Args:
        df:                The DataFrame to validate.
        semantic_profile:  Output of ``semantic_profile_dataframe(df)``.
        config:            Optional overrides merged with DEFAULT_VALIDATOR_CONFIG.

    Returns:
        (valid_leads_df, rejected_leads_df, validation_report)

        valid_leads_df:    Rows with all email columns passing validation.
        rejected_leads_df: Rows that failed validation, with a
                           ``DataForge_Rejection_Reason`` column explaining why.
        validation_report: Dict with counts of issues found.
    """
    cfg = {**DEFAULT_VALIDATOR_CONFIG, **(config or {})}
    col_meta = semantic_profile.get("columns", {})

    email_columns = [
        col_name
        for col_name, meta in col_meta.items()
        if meta.get("semantic_type") == "email" and col_name in df.columns
    ]

    result_df = df.copy()

    # Track per-row rejection reasons and role-based flags.
    rejection_reasons = [""] * len(result_df)
    role_flags = [False] * len(result_df)

    invalid_email_count = 0
    blank_email_count = 0
    role_based_email_count = 0

    for col_name in email_columns:
        for idx in range(len(result_df)):
            value = result_df[col_name].iloc[idx]

            # ── Check blank / missing ────────────────────────────────────
            if _is_blank(value):
                if cfg["reject_blank_emails"] and not rejection_reasons[idx]:
                    rejection_reasons[idx] = "BLANK_EMAIL"
                    blank_email_count += 1
                continue

            str_value = str(value).strip()

            # ── Check format ─────────────────────────────────────────────
            if cfg["strict_email_validation"] and not _is_valid_email(str_value):
                if not rejection_reasons[idx]:
                    reason = _classify_rejection(str_value)
                    rejection_reasons[idx] = reason
                    if reason == "BLANK_EMAIL":
                        blank_email_count += 1
                    else:
                        invalid_email_count += 1
                continue

            # ── Check role-based ─────────────────────────────────────────
            if cfg["flag_role_accounts"] and _is_role_based(str_value):
                role_flags[idx] = True
                role_based_email_count += 1

    # ── Split into valid / rejected ──────────────────────────────────────
    is_rejected = [bool(r) for r in rejection_reasons]

    valid_mask = [not r for r in is_rejected]
    rejected_mask = is_rejected

    valid_df = result_df.loc[valid_mask].copy().reset_index(drop=True)
    rejected_df = result_df.loc[rejected_mask].copy().reset_index(drop=True)

    # Add rejection reason column to rejected rows.
    rejected_reasons_filtered = [
        rejection_reasons[i] for i in range(len(result_df)) if rejected_mask[i]
    ]
    rejected_df["DataForge_Rejection_Reason"] = rejected_reasons_filtered

    # Add role-based flag to valid rows.
    if cfg["flag_role_accounts"]:
        valid_role_flags = [
            role_flags[i] for i in range(len(result_df)) if valid_mask[i]
        ]
        valid_df["DataForge_Role_Based_Email"] = valid_role_flags

    report = {
        "total_rows": len(df),
        "valid_rows": len(valid_df),
        "rejected_rows": len(rejected_df),
        "invalid_email_count": invalid_email_count,
        "blank_email_count": blank_email_count,
        "role_based_email_count": role_based_email_count,
    }

    return valid_df, rejected_df, report


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

def _is_blank(value) -> bool:
    """Check if a value is blank, None, NaN, or an empty string."""
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _is_valid_email(value: str) -> bool:
    """Validate email format using deterministic regex.

    Rejects:
        - Missing @
        - Missing domain
        - Malformed domains (localhost, no TLD, trailing dot)
        - Whitespace anywhere in the string
    """
    if " " in value or "\t" in value:
        return False
    return bool(EMAIL_RE.match(value))


def _is_role_based(value: str) -> bool:
    """Check if an email uses a role-based prefix (info@, sales@, etc.)."""
    local_part = value.split("@")[0].lower()
    return local_part in ROLE_PREFIXES


def _classify_rejection(value: str) -> str:
    """Determine the specific rejection reason for an invalid email.

    Returns one of:
        BLANK_EMAIL          — empty string after stripping
        INVALID_DOMAIN       — missing or malformed domain part
        INVALID_EMAIL_FORMAT — catch-all for other format failures
    """
    stripped = value.strip()
    if not stripped:
        return "BLANK_EMAIL"

    # Check for domain-related issues.
    if "@" in stripped:
        parts = stripped.split("@", 1)
        domain = parts[1] if len(parts) > 1 else ""
        if not domain or "." not in domain or domain.startswith(".") or domain.endswith("."):
            return "INVALID_DOMAIN"

    return "INVALID_EMAIL_FORMAT"
