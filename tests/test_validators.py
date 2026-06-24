import pandas as pd
import numpy as np

from src.core.validators import (
    validate_leads,
    _is_valid_email,
    _is_blank,
    _is_role_based,
    _classify_rejection,
)
from src.core.semantic_profiler import semantic_profile_dataframe


def _make_manual_profile(columns_meta: dict) -> dict:
    """Helper: build a minimal semantic profile dict by hand for isolation tests."""
    columns = {}
    summary = {}
    for col_name, sem_type in columns_meta.items():
        columns[col_name] = {
            "semantic_type": sem_type,
            "confidence": 1.0,
            "reason": "manual test profile",
            "header_matched": False,
            "sample_size": 0,
            "match_count": 0,
            "detector": "test",
        }
        summary.setdefault(sem_type, []).append(col_name)
    return {"columns": columns, "detected_types_summary": summary}


# ─────────────────────────────────────────────
# Rule 1: Valid email format
# ─────────────────────────────────────────────


def test_valid_email_passes():
    df = pd.DataFrame({"email": ["john@example.com", "piyush@gmail.com", "sales.team@company.io"]})
    profile = _make_manual_profile({"email": "email"})
    valid, rejected, report = validate_leads(df, profile)

    assert len(valid) == 3
    assert len(rejected) == 0
    assert report["valid_rows"] == 3
    assert report["rejected_rows"] == 0


def test_missing_at_rejected():
    df = pd.DataFrame({"email": ["john@example.com", "invalidemail"]})
    profile = _make_manual_profile({"email": "email"})
    valid, rejected, report = validate_leads(df, profile)

    assert len(valid) == 1
    assert len(rejected) == 1
    assert rejected["DataForge_Rejection_Reason"].iloc[0] == "INVALID_EMAIL_FORMAT"


def test_missing_domain_rejected():
    df = pd.DataFrame({"email": ["john@", "@example.com", "john@.com"]})
    profile = _make_manual_profile({"email": "email"})
    valid, rejected, report = validate_leads(df, profile)

    assert len(valid) == 0
    assert len(rejected) == 3


def test_double_at_rejected():
    df = pd.DataFrame({"email": ["john@@example.com"]})
    profile = _make_manual_profile({"email": "email"})
    valid, rejected, _ = validate_leads(df, profile)

    assert len(valid) == 0
    assert len(rejected) == 1


def test_dot_only_domain_rejected():
    df = pd.DataFrame({"email": ["john@example.com", "john@domain.", "john@domain"]})
    profile = _make_manual_profile({"email": "email"})
    valid, rejected, _ = validate_leads(df, profile)

    assert len(valid) == 1
    assert valid["email"].iloc[0] == "john@example.com"
    assert len(rejected) == 2


def test_no_dot_in_email_rejected():
    df = pd.DataFrame({"email": ["john.example.com"]})
    profile = _make_manual_profile({"email": "email"})
    valid, rejected, _ = validate_leads(df, profile)

    assert len(valid) == 0
    assert len(rejected) == 1
    assert rejected["DataForge_Rejection_Reason"].iloc[0] == "INVALID_EMAIL_FORMAT"


# ─────────────────────────────────────────────
# Rule 2: Blank emails
# ─────────────────────────────────────────────


def test_blank_email_rejected():
    df = pd.DataFrame({"email": ["john@example.com", ""]})
    profile = _make_manual_profile({"email": "email"})
    valid, rejected, report = validate_leads(df, profile)

    assert len(valid) == 1
    assert len(rejected) == 1
    assert rejected["DataForge_Rejection_Reason"].iloc[0] == "BLANK_EMAIL"
    assert report["blank_email_count"] == 1


def test_none_rejected():
    df = pd.DataFrame({"email": ["john@example.com", None]})
    profile = _make_manual_profile({"email": "email"})
    valid, rejected, report = validate_leads(df, profile)

    assert len(valid) == 1
    assert len(rejected) == 1
    assert rejected["DataForge_Rejection_Reason"].iloc[0] == "BLANK_EMAIL"
    assert report["blank_email_count"] == 1


def test_nan_rejected():
    df = pd.DataFrame({"email": ["john@example.com", np.nan]})
    profile = _make_manual_profile({"email": "email"})
    valid, rejected, report = validate_leads(df, profile)

    assert len(valid) == 1
    assert len(rejected) == 1
    assert rejected["DataForge_Rejection_Reason"].iloc[0] == "BLANK_EMAIL"


def test_whitespace_only_rejected():
    df = pd.DataFrame({"email": ["   ", "\t"]})
    profile = _make_manual_profile({"email": "email"})
    valid, rejected, report = validate_leads(df, profile)

    assert len(valid) == 0
    assert len(rejected) == 2


# ─────────────────────────────────────────────
# Rule 3: Malformed domains
# ─────────────────────────────────────────────


def test_localhost_rejected():
    df = pd.DataFrame({"email": ["john@localhost"]})
    profile = _make_manual_profile({"email": "email"})
    valid, rejected, _ = validate_leads(df, profile)

    assert len(valid) == 0
    assert len(rejected) == 1
    assert rejected["DataForge_Rejection_Reason"].iloc[0] == "INVALID_DOMAIN"


def test_domain_starting_with_dot_rejected():
    df = pd.DataFrame({"email": ["john@.com"]})
    profile = _make_manual_profile({"email": "email"})
    _, rejected, _ = validate_leads(df, profile)

    assert len(rejected) == 1
    assert rejected["DataForge_Rejection_Reason"].iloc[0] == "INVALID_DOMAIN"


def test_domain_ending_with_dot_rejected():
    df = pd.DataFrame({"email": ["john@domain."]})
    profile = _make_manual_profile({"email": "email"})
    _, rejected, _ = validate_leads(df, profile)

    assert len(rejected) == 1
    assert rejected["DataForge_Rejection_Reason"].iloc[0] == "INVALID_DOMAIN"


# ─────────────────────────────────────────────
# Rule 4: Whitespace in emails
# ─────────────────────────────────────────────


def test_whitespace_in_email_rejected():
    df = pd.DataFrame({"email": ["john @example.com", "john@ example.com"]})
    profile = _make_manual_profile({"email": "email"})
    valid, rejected, _ = validate_leads(df, profile)

    assert len(valid) == 0
    assert len(rejected) == 2


# ─────────────────────────────────────────────
# Role-based email detection
# ─────────────────────────────────────────────


def test_role_email_flagged():
    df = pd.DataFrame({"email": ["info@company.com", "sales@corp.io", "john@example.com"]})
    profile = _make_manual_profile({"email": "email"})
    valid, rejected, report = validate_leads(df, profile)

    assert len(valid) == 3  # NOT rejected
    assert len(rejected) == 0
    assert report["role_based_email_count"] == 2

    # Check the flag column.
    assert valid["DataForge_Role_Based_Email"].iloc[0] == True
    assert valid["DataForge_Role_Based_Email"].iloc[1] == True
    assert valid["DataForge_Role_Based_Email"].iloc[2] == False


def test_role_email_not_rejected():
    df = pd.DataFrame({"email": ["support@example.com"]})
    profile = _make_manual_profile({"email": "email"})
    valid, rejected, report = validate_leads(df, profile)

    assert len(valid) == 1
    assert len(rejected) == 0
    assert report["role_based_email_count"] == 1


def test_role_email_all_prefixes():
    prefixes = ["info", "sales", "support", "admin", "contact", "hello", "team"]
    emails = [f"{p}@company.com" for p in prefixes]
    df = pd.DataFrame({"email": emails})
    profile = _make_manual_profile({"email": "email"})
    valid, _, report = validate_leads(df, profile)

    assert len(valid) == len(prefixes)
    assert report["role_based_email_count"] == len(prefixes)
    assert all(valid["DataForge_Role_Based_Email"])


def test_non_role_email_not_flagged():
    df = pd.DataFrame({"email": ["piyush@company.com", "john.doe@test.io"]})
    profile = _make_manual_profile({"email": "email"})
    valid, _, report = validate_leads(df, profile)

    assert report["role_based_email_count"] == 0
    assert not any(valid["DataForge_Role_Based_Email"])


# ─────────────────────────────────────────────
# Rejection reason tracking
# ─────────────────────────────────────────────


def test_rejection_reason_populated():
    df = pd.DataFrame({"email": ["invalidemail", None, "john@localhost", "john @x.com"]})
    profile = _make_manual_profile({"email": "email"})
    _, rejected, _ = validate_leads(df, profile)

    assert len(rejected) == 4
    reasons = rejected["DataForge_Rejection_Reason"].tolist()
    assert "INVALID_EMAIL_FORMAT" in reasons
    assert "BLANK_EMAIL" in reasons
    assert "INVALID_DOMAIN" in reasons
    assert all(r != "" for r in reasons)


def test_rejection_reason_not_on_valid():
    df = pd.DataFrame({"email": ["john@example.com"]})
    profile = _make_manual_profile({"email": "email"})
    valid, _, _ = validate_leads(df, profile)

    assert "DataForge_Rejection_Reason" not in valid.columns


# ─────────────────────────────────────────────
# Report accuracy
# ─────────────────────────────────────────────


def test_report_counts_accurate():
    df = pd.DataFrame({
        "email": [
            "john@example.com",      # valid
            "invalidemail",           # invalid format
            "info@company.com",       # valid + role-based
            None,                     # blank
            "jane@test.io",           # valid
            "",                       # blank
        ],
    })
    profile = _make_manual_profile({"email": "email"})
    valid, rejected, report = validate_leads(df, profile)

    assert report["total_rows"] == 6
    assert report["valid_rows"] == 3
    assert report["rejected_rows"] == 3
    assert report["invalid_email_count"] == 1
    assert report["blank_email_count"] == 2
    assert report["role_based_email_count"] == 1


# ─────────────────────────────────────────────
# Multiple invalid rows
# ─────────────────────────────────────────────


def test_multiple_invalid_rows():
    df = pd.DataFrame({
        "email": ["bad1", "bad2", "bad3", None, "john@example.com"],
    })
    profile = _make_manual_profile({"email": "email"})
    valid, rejected, report = validate_leads(df, profile)

    assert len(valid) == 1
    assert len(rejected) == 4
    assert report["invalid_email_count"] == 3
    assert report["blank_email_count"] == 1


# ─────────────────────────────────────────────
# Multiple email columns
# ─────────────────────────────────────────────


def test_multiple_email_columns():
    df = pd.DataFrame({
        "primary_email": ["john@example.com", "bad_email", "jane@test.io"],
        "secondary_email": ["backup@example.com", "also_bad", "alt@test.io"],
    })
    profile = _make_manual_profile({
        "primary_email": "email",
        "secondary_email": "email",
    })
    valid, rejected, report = validate_leads(df, profile)

    # Row 1 (index 1) has invalid emails in both columns.
    assert len(rejected) >= 1
    assert report["invalid_email_count"] >= 1


def test_non_email_columns_untouched():
    df = pd.DataFrame({
        "email": ["john@example.com", "bad_email"],
        "name": ["John Smith", "Jane Doe"],
        "phone": ["+91 9876543210", "+1 555-1234"],
    })
    profile = _make_manual_profile({
        "email": "email",
        "name": "full_name",
        "phone": "phone_number",
    })
    valid, rejected, _ = validate_leads(df, profile)

    # Name and phone columns should pass through unchanged.
    assert valid["name"].iloc[0] == "John Smith"
    assert rejected["name"].iloc[0] == "Jane Doe"
    assert "phone" in valid.columns
    assert "phone" in rejected.columns


# ─────────────────────────────────────────────
# Config overrides
# ─────────────────────────────────────────────


def test_config_disable_blank_rejection():
    df = pd.DataFrame({"email": [None, "", "john@example.com"]})
    profile = _make_manual_profile({"email": "email"})
    valid, rejected, report = validate_leads(
        df, profile, config={"reject_blank_emails": False}
    )

    # Blank emails should NOT be rejected when disabled.
    assert len(valid) == 3
    assert len(rejected) == 0
    assert report["blank_email_count"] == 0


def test_config_disable_role_flagging():
    df = pd.DataFrame({"email": ["info@company.com", "john@example.com"]})
    profile = _make_manual_profile({"email": "email"})
    valid, _, report = validate_leads(
        df, profile, config={"flag_role_accounts": False}
    )

    assert report["role_based_email_count"] == 0
    assert "DataForge_Role_Based_Email" not in valid.columns


def test_config_disable_strict_validation():
    df = pd.DataFrame({"email": ["john@localhost", "john@example.com"]})
    profile = _make_manual_profile({"email": "email"})
    valid, rejected, report = validate_leads(
        df, profile, config={"strict_email_validation": False}
    )

    # Even invalid formats should pass when strict validation is off.
    assert len(valid) == 2
    assert len(rejected) == 0


# ─────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────


def test_empty_dataframe():
    df = pd.DataFrame({"email": pd.Series([], dtype="object")})
    profile = _make_manual_profile({"email": "email"})
    valid, rejected, report = validate_leads(df, profile)

    assert len(valid) == 0
    assert len(rejected) == 0
    assert report["total_rows"] == 0
    assert report["valid_rows"] == 0
    assert report["rejected_rows"] == 0


def test_no_email_columns():
    df = pd.DataFrame({"name": ["John", "Jane"], "age": [25, 30]})
    profile = _make_manual_profile({"name": "first_name", "age": "unknown"})
    valid, rejected, report = validate_leads(df, profile)

    # No email columns → all rows pass through as valid.
    assert len(valid) == 2
    assert len(rejected) == 0


def test_all_valid():
    df = pd.DataFrame({
        "email": ["a@b.com", "c@d.io", "e@f.org"],
    })
    profile = _make_manual_profile({"email": "email"})
    valid, rejected, report = validate_leads(df, profile)

    assert len(valid) == 3
    assert len(rejected) == 0
    assert report["rejected_rows"] == 0


def test_all_rejected():
    df = pd.DataFrame({
        "email": ["bad1", "bad2", None],
    })
    profile = _make_manual_profile({"email": "email"})
    valid, rejected, report = validate_leads(df, profile)

    assert len(valid) == 0
    assert len(rejected) == 3


def test_valid_df_preserves_all_columns():
    df = pd.DataFrame({
        "email": ["john@example.com"],
        "name": ["John Smith"],
        "company": ["Acme Inc"],
    })
    profile = _make_manual_profile({
        "email": "email",
        "name": "full_name",
        "company": "company_name",
    })
    valid, _, _ = validate_leads(df, profile)

    assert "email" in valid.columns
    assert "name" in valid.columns
    assert "company" in valid.columns


def test_rejected_df_preserves_all_columns():
    df = pd.DataFrame({
        "email": ["bad_email"],
        "name": ["John Smith"],
        "company": ["Acme Inc"],
    })
    profile = _make_manual_profile({
        "email": "email",
        "name": "full_name",
        "company": "company_name",
    })
    _, rejected, _ = validate_leads(df, profile)

    assert "email" in rejected.columns
    assert "name" in rejected.columns
    assert "company" in rejected.columns
    assert "DataForge_Rejection_Reason" in rejected.columns


# ─────────────────────────────────────────────
# Integration with DF-001 semantic profiler
# ─────────────────────────────────────────────


def test_integration_with_real_semantic_profiler():
    df = pd.DataFrame({
        "email": [
            "john@example.com",
            "invalidemail",
            "info@company.com",
            None,
        ],
        "name": ["John Smith", "Jane Doe", "Bob Williams", "Alice Brown"],
    })
    profile = semantic_profile_dataframe(df)
    valid, rejected, report = validate_leads(df, profile)

    assert report["valid_rows"] == 2
    assert report["rejected_rows"] == 2
    assert report["role_based_email_count"] == 1


# ─────────────────────────────────────────────
# Acceptance criteria (exact ticket scenario)
# ─────────────────────────────────────────────


def test_acceptance_criteria():
    """The exact acceptance criteria from the DF-003 ticket."""
    df = pd.DataFrame({
        "email": ["john@example.com", "invalidemail", "info@company.com", None],
    })
    profile = _make_manual_profile({"email": "email"})
    valid, rejected, report = validate_leads(df, profile)

    assert report["valid_rows"] == 2
    assert report["rejected_rows"] == 2
    assert report["role_based_email_count"] == 1

    assert valid["email"].tolist() == ["john@example.com", "info@company.com"]

    rejected_emails = rejected["email"].tolist()
    assert "invalidemail" in rejected_emails

    reasons = rejected["DataForge_Rejection_Reason"].tolist()
    assert "INVALID_EMAIL_FORMAT" in reasons
    assert "BLANK_EMAIL" in reasons


# ─────────────────────────────────────────────
# Internal helper unit tests
# ─────────────────────────────────────────────


def test_is_valid_email_unit():
    assert _is_valid_email("john@example.com") is True
    assert _is_valid_email("a@b.io") is True
    assert _is_valid_email("sales+west@company.org") is True

    assert _is_valid_email("invalidemail") is False
    assert _is_valid_email("john@") is False
    assert _is_valid_email("@example.com") is False
    assert _is_valid_email("john@@example.com") is False
    assert _is_valid_email("john @example.com") is False
    assert _is_valid_email("john@localhost") is False
    assert _is_valid_email("john@domain.") is False


def test_is_blank_unit():
    assert _is_blank(None) is True
    assert _is_blank(np.nan) is True
    assert _is_blank("") is True
    assert _is_blank("   ") is True
    assert _is_blank("john@example.com") is False


def test_is_role_based_unit():
    assert _is_role_based("info@company.com") is True
    assert _is_role_based("sales@corp.io") is True
    assert _is_role_based("support@test.com") is True
    assert _is_role_based("john@example.com") is False
    assert _is_role_based("piyush@gmail.com") is False


def test_classify_rejection_unit():
    assert _classify_rejection("invalidemail") == "INVALID_EMAIL_FORMAT"
    assert _classify_rejection("john@") == "INVALID_DOMAIN"
    assert _classify_rejection("john@localhost") == "INVALID_DOMAIN"
    assert _classify_rejection("john@.com") == "INVALID_DOMAIN"
    assert _classify_rejection("john@domain.") == "INVALID_DOMAIN"
    assert _classify_rejection("") == "BLANK_EMAIL"
    assert _classify_rejection("   ") == "BLANK_EMAIL"
