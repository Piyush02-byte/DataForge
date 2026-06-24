import pandas as pd
import numpy as np

from src.core.crm_formatter import format_for_crm, _smart_title_case, _capitalize_token
from src.core.semantic_profiler import semantic_profile_dataframe


def _make_profile(df):
    """Helper: run the real semantic profiler against a DataFrame."""
    return semantic_profile_dataframe(df)


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
# Transformation 1: Title Case Names
# ─────────────────────────────────────────────


def test_title_case_all_caps():
    df = pd.DataFrame({"name": ["PIYUSH KUMAR", "ANKIT SHARMA", "RAVI SINGH"]})
    profile = _make_manual_profile({"name": "full_name"})
    cleaned, report = format_for_crm(df, profile)

    assert cleaned["name"].tolist() == ["Piyush Kumar", "Ankit Sharma", "Ravi Singh"]
    assert report["name_fields_formatted"] == 3


def test_title_case_all_lower():
    df = pd.DataFrame({"name": ["john smith", "jane doe"]})
    profile = _make_manual_profile({"name": "full_name"})
    cleaned, _ = format_for_crm(df, profile)

    assert cleaned["name"].tolist() == ["John Smith", "Jane Doe"]


def test_title_case_mixed_garbage():
    df = pd.DataFrame({"name": ["mARY-jANE watson", "PIyUsH KuMaR"]})
    profile = _make_manual_profile({"name": "full_name"})
    cleaned, _ = format_for_crm(df, profile)

    assert cleaned["name"].tolist() == ["Mary-Jane Watson", "Piyush Kumar"]


def test_title_case_hyphenated_names():
    df = pd.DataFrame({"first_name": ["mary-jane", "JEAN-CLAUDE"]})
    profile = _make_manual_profile({"first_name": "first_name"})
    cleaned, _ = format_for_crm(df, profile)

    assert cleaned["first_name"].tolist() == ["Mary-Jane", "Jean-Claude"]


def test_title_case_apostrophe_names():
    df = pd.DataFrame({"last_name": ["o'brien", "O'NEILL", "d'souza"]})
    profile = _make_manual_profile({"last_name": "last_name"})
    cleaned, _ = format_for_crm(df, profile)

    assert cleaned["last_name"].tolist() == ["O'Brien", "O'Neill", "D'Souza"]


def test_title_case_already_correct():
    df = pd.DataFrame({"name": ["Piyush Kumar", "John Smith"]})
    profile = _make_manual_profile({"name": "full_name"})
    cleaned, report = format_for_crm(df, profile)

    assert cleaned["name"].tolist() == ["Piyush Kumar", "John Smith"]
    assert report["name_fields_formatted"] == 0  # no changes needed


def test_title_case_first_name_column():
    df = pd.DataFrame({"first": ["piyush", "ANKIT", "rAvI"]})
    profile = _make_manual_profile({"first": "first_name"})
    cleaned, report = format_for_crm(df, profile)

    assert cleaned["first"].tolist() == ["Piyush", "Ankit", "Ravi"]
    assert report["name_fields_formatted"] == 3


def test_title_case_last_name_column():
    df = pd.DataFrame({"last": ["KUMAR", "sharma", "SiNgH"]})
    profile = _make_manual_profile({"last": "last_name"})
    cleaned, report = format_for_crm(df, profile)

    assert cleaned["last"].tolist() == ["Kumar", "Sharma", "Singh"]
    assert report["name_fields_formatted"] == 3


# ─────────────────────────────────────────────
# Transformation 2: Lowercase Emails
# ─────────────────────────────────────────────


def test_lowercase_emails():
    df = pd.DataFrame({"email": ["JOHN@EXAMPLE.COM", "Sales@Company.IO"]})
    profile = _make_manual_profile({"email": "email"})
    cleaned, report = format_for_crm(df, profile)

    assert cleaned["email"].tolist() == ["john@example.com", "sales@company.io"]
    assert report["email_fields_normalized"] == 2


def test_lowercase_email_already_lowercase():
    df = pd.DataFrame({"email": ["john@example.com", "jane@test.io"]})
    profile = _make_manual_profile({"email": "email"})
    cleaned, report = format_for_crm(df, profile)

    assert cleaned["email"].tolist() == ["john@example.com", "jane@test.io"]
    assert report["email_fields_normalized"] == 0


# ─────────────────────────────────────────────
# Transformation 3: Whitespace Cleanup
# ─────────────────────────────────────────────


def test_whitespace_trimming():
    df = pd.DataFrame({"name": ["  Piyush Kumar  ", "  John  "]})
    profile = _make_manual_profile({"name": "full_name"})
    cleaned, report = format_for_crm(df, profile)

    assert cleaned["name"].tolist() == ["Piyush Kumar", "John"]
    assert report["whitespace_fixes"] == 2


def test_whitespace_no_changes_needed():
    df = pd.DataFrame({"name": ["Piyush", "Ankit"]})
    profile = _make_manual_profile({"name": "first_name"})
    cleaned, report = format_for_crm(df, profile)

    assert report["whitespace_fixes"] == 0


def test_whitespace_on_non_name_columns():
    df = pd.DataFrame({"company": ["  Google LLC  ", "  Infosys Ltd  "]})
    profile = _make_manual_profile({"company": "company_name"})
    cleaned, report = format_for_crm(df, profile)

    # Whitespace trimming applies to ALL string columns, not just names.
    assert cleaned["company"].tolist() == ["Google LLC", "Infosys Ltd"]
    assert report["whitespace_fixes"] == 2


# ─────────────────────────────────────────────
# Transformation 4: Full Name Splitting
# ─────────────────────────────────────────────


def test_full_name_splitting():
    df = pd.DataFrame({"name": ["Piyush Kumar", "Ankit Sharma"]})
    profile = _make_manual_profile({"name": "full_name"})
    cleaned, report = format_for_crm(df, profile)

    assert "first_name" in cleaned.columns
    assert "last_name" in cleaned.columns
    assert cleaned["first_name"].tolist() == ["Piyush", "Ankit"]
    assert cleaned["last_name"].tolist() == ["Kumar", "Sharma"]
    assert report["full_names_split"] == 2


def test_full_name_multi_token_last_name():
    df = pd.DataFrame({"name": ["John Ronald Smith", "Mary Jane Watson"]})
    profile = _make_manual_profile({"name": "full_name"})
    cleaned, _ = format_for_crm(df, profile)

    assert cleaned["first_name"].tolist() == ["John", "Mary"]
    assert cleaned["last_name"].tolist() == ["Ronald Smith", "Jane Watson"]


def test_full_name_original_column_preserved():
    df = pd.DataFrame({"name": ["Piyush Kumar"]})
    profile = _make_manual_profile({"name": "full_name"})
    cleaned, _ = format_for_crm(df, profile)

    assert "name" in cleaned.columns
    assert cleaned["name"].tolist() == ["Piyush Kumar"]


def test_full_name_split_column_ordering():
    df = pd.DataFrame({"name": ["Piyush Kumar"], "email": ["p@e.com"]})
    profile = _make_manual_profile({"name": "full_name", "email": "email"})
    cleaned, _ = format_for_crm(df, profile)

    # first_name and last_name should be inserted right after the full_name column.
    cols = cleaned.columns.tolist()
    assert cols == ["name", "first_name", "last_name", "email"]


def test_full_name_split_skipped_if_first_name_exists():
    df = pd.DataFrame({
        "name": ["Piyush Kumar"],
        "first_name": ["Piyush"],
    })
    profile = _make_manual_profile({"name": "full_name", "first_name": "first_name"})
    cleaned, report = format_for_crm(df, profile)

    # Should NOT create duplicate first_name/last_name columns.
    assert report["full_names_split"] == 0
    assert "last_name" not in cleaned.columns


def test_full_name_split_skipped_if_last_name_exists():
    df = pd.DataFrame({
        "name": ["Piyush Kumar"],
        "last_name": ["Kumar"],
    })
    profile = _make_manual_profile({"name": "full_name", "last_name": "last_name"})
    cleaned, report = format_for_crm(df, profile)

    assert report["full_names_split"] == 0


# ─────────────────────────────────────────────
# Config Overrides
# ─────────────────────────────────────────────


def test_config_disable_split():
    df = pd.DataFrame({"name": ["Piyush Kumar"]})
    profile = _make_manual_profile({"name": "full_name"})
    cleaned, report = format_for_crm(df, profile, config={"split_full_names": False})

    assert "first_name" not in cleaned.columns
    assert "last_name" not in cleaned.columns
    assert report["full_names_split"] == 0


def test_config_disable_email_normalize():
    df = pd.DataFrame({"email": ["JOHN@EXAMPLE.COM"]})
    profile = _make_manual_profile({"email": "email"})
    cleaned, report = format_for_crm(df, profile, config={"normalize_emails": False})

    assert cleaned["email"].tolist() == ["JOHN@EXAMPLE.COM"]
    assert report["email_fields_normalized"] == 0


def test_config_disable_title_case():
    df = pd.DataFrame({"name": ["PIYUSH KUMAR"]})
    profile = _make_manual_profile({"name": "full_name"})
    cleaned, report = format_for_crm(df, profile, config={"title_case_names": False})

    assert cleaned["name"].tolist() == ["PIYUSH KUMAR"]
    assert report["name_fields_formatted"] == 0


def test_config_disable_whitespace():
    df = pd.DataFrame({"name": ["  Piyush  "]})
    profile = _make_manual_profile({"name": "first_name"})
    # Must also disable title_case_names because title casing uses split/join
    # which strips whitespace as a side effect.
    cleaned, report = format_for_crm(
        df, profile, config={"trim_whitespace": False, "title_case_names": False}
    )

    assert cleaned["name"].tolist() == ["  Piyush  "]
    assert report["whitespace_fixes"] == 0


# ─────────────────────────────────────────────
# Edge Cases
# ─────────────────────────────────────────────


def test_empty_dataframe():
    df = pd.DataFrame({"name": pd.Series([], dtype="object")})
    profile = _make_manual_profile({"name": "full_name"})
    cleaned, report = format_for_crm(df, profile)

    assert len(cleaned) == 0
    assert report["name_fields_formatted"] == 0
    assert report["full_names_split"] == 0


def test_null_values_preserved():
    df = pd.DataFrame({"name": ["Piyush Kumar", None, np.nan]})
    profile = _make_manual_profile({"name": "full_name"})
    cleaned, _ = format_for_crm(df, profile)

    assert cleaned["name"].iloc[0] == "Piyush Kumar"
    assert cleaned["name"].iloc[1] is None
    assert pd.isna(cleaned["name"].iloc[2])


def test_non_semantic_columns_untouched():
    df = pd.DataFrame({
        "name": ["piyush kumar"],
        "age": [23],
        "notes": ["some random text"],
    })
    profile = _make_manual_profile({
        "name": "full_name",
        "age": "unknown",
        "notes": "unknown",
    })
    cleaned, _ = format_for_crm(df, profile)

    assert cleaned["age"].tolist() == [23]
    # notes should only have whitespace trimming, not title casing.
    assert cleaned["notes"].tolist() == ["some random text"]


# ─────────────────────────────────────────────
# Report Accuracy
# ─────────────────────────────────────────────


def test_report_counts_accuracy():
    df = pd.DataFrame({
        "name": ["  PIYUSH KUMAR  ", "john smith"],
        "email": ["PIYUSH@MAIL.COM", "jane@test.io"],
    })
    profile = _make_manual_profile({"name": "full_name", "email": "email"})
    cleaned, report = format_for_crm(df, profile)

    # Whitespace: 1 name had leading/trailing whitespace (trimmed first).
    assert report["whitespace_fixes"] >= 1

    # Names: Both names were not title case after trimming.
    assert report["name_fields_formatted"] == 2

    # Emails: 1 email was uppercase.
    assert report["email_fields_normalized"] == 1

    # Split: Both full names should be split.
    assert report["full_names_split"] == 2


# ─────────────────────────────────────────────
# Integration: Full acceptance criteria
# ─────────────────────────────────────────────


def test_acceptance_criteria():
    """The exact acceptance criteria from the DF-002 ticket."""
    df = pd.DataFrame({
        "name": [" PIYUSH KUMAR "],
        "email": ["PIYUSH@MAIL.COM"],
    })
    profile = _make_manual_profile({"name": "full_name", "email": "email"})
    cleaned, report = format_for_crm(df, profile)

    assert cleaned["name"].iloc[0] == "Piyush Kumar"
    assert cleaned["first_name"].iloc[0] == "Piyush"
    assert cleaned["last_name"].iloc[0] == "Kumar"
    assert cleaned["email"].iloc[0] == "piyush@mail.com"

    assert report["name_fields_formatted"] >= 1
    assert report["email_fields_normalized"] == 1
    assert report["whitespace_fixes"] >= 1
    assert report["full_names_split"] == 1


def test_integration_with_real_semantic_profiler():
    """End-to-end: use the actual semantic profiler to generate the profile."""
    df = pd.DataFrame({
        "email": ["JOHN@EXAMPLE.COM", "JANE@TEST.IO", "BOB@CORP.COM"],
        "name": ["  john smith  ", "  JANE DOE  ", "  bob williams  "],
    })
    profile = semantic_profile_dataframe(df)
    cleaned, report = format_for_crm(df, profile)

    assert cleaned["email"].tolist() == ["john@example.com", "jane@test.io", "bob@corp.com"]
    assert cleaned["name"].tolist() == ["John Smith", "Jane Doe", "Bob Williams"]
    assert report["email_fields_normalized"] == 3
    assert report["name_fields_formatted"] == 3
    assert report["whitespace_fixes"] >= 3


# ─────────────────────────────────────────────
# Internal helper tests
# ─────────────────────────────────────────────


def test_smart_title_case_unit():
    assert _smart_title_case("PIYUSH KUMAR") == "Piyush Kumar"
    assert _smart_title_case("john smith") == "John Smith"
    assert _smart_title_case("mARY-jANE watson") == "Mary-Jane Watson"
    assert _smart_title_case("john o'brien") == "John O'Brien"


def test_capitalize_token_unit():
    assert _capitalize_token("piyush") == "Piyush"
    assert _capitalize_token("o'brien") == "O'Brien"
    assert _capitalize_token("KUMAR") == "Kumar"
