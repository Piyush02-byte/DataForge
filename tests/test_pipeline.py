import pandas as pd
import numpy as np
import pytest

from src.core.pipeline import process_lead_list


# ─────────────────────────────────────────────
# End-to-end happy path
# ─────────────────────────────────────────────


def test_end_to_end_happy_path():
    df = pd.DataFrame({
        "name": [
            "  PIYUSH KUMAR  ",
            "John",
            "John Smith",
            "John S.",
        ],
        "email": [
            "PIYUSH@MAIL.COM",
            "invalidemail",
            "john@example.com",
            "john@example.com",
        ],
    })
    result = process_lead_list(df)

    crm = result["crm_ready_df"]
    rejected = result["rejected_df"]
    report = result["report"]

    # "invalidemail" should be rejected.
    assert len(rejected) >= 1

    # Piyush should be formatted + valid.
    assert report["input_rows"] == 4
    assert report["output_rows"] >= 1
    assert "crm_formatting" in report
    assert "validation" in report
    assert "deduplication" in report


def test_end_to_end_returns_all_keys():
    df = pd.DataFrame({
        "email": ["a@b.com", "c@d.com", "e@f.com"],
    })
    result = process_lead_list(df)

    assert "crm_ready_df" in result
    assert "rejected_df" in result
    assert "report" in result
    assert isinstance(result["crm_ready_df"], pd.DataFrame)
    assert isinstance(result["rejected_df"], pd.DataFrame)
    assert isinstance(result["report"], dict)


# ─────────────────────────────────────────────
# Input validation
# ─────────────────────────────────────────────


def test_empty_dataframe_raises():
    df = pd.DataFrame({"email": pd.Series([], dtype="object")})
    with pytest.raises(ValueError, match="empty"):
        process_lead_list(df)


def test_non_dataframe_raises():
    with pytest.raises(TypeError, match="DataFrame"):
        process_lead_list([1, 2, 3])


def test_non_dataframe_dict_raises():
    with pytest.raises(TypeError, match="DataFrame"):
        process_lead_list({"email": ["a@b.com"]})


# ─────────────────────────────────────────────
# No email column
# ─────────────────────────────────────────────


def test_no_email_column_does_not_fail():
    df = pd.DataFrame({
        "name": ["Piyush Kumar", "Ankit Sharma", "Ravi Singh"],
        "phone": ["+91 9876543210", "+1 555 1234", "+44 20 7946"],
    })
    result = process_lead_list(df)

    # All rows pass through since no email validation applies.
    assert len(result["crm_ready_df"]) == 3
    assert len(result["rejected_df"]) == 0


def test_no_email_column_report_structure():
    df = pd.DataFrame({
        "name": ["Piyush Kumar", "Ankit Sharma", "Ravi Singh"],
    })
    result = process_lead_list(df)
    report = result["report"]

    assert report["input_rows"] == 3
    assert report["output_rows"] == 3
    assert report["rejected_rows"] == 0


# ─────────────────────────────────────────────
# Formatting integration
# ─────────────────────────────────────────────


def test_formatting_title_cases_names():
    df = pd.DataFrame({
        "name": ["PIYUSH KUMAR", "john smith", "JANE DOE"],
        "email": ["a@b.com", "c@d.com", "e@f.com"],
    })
    result = process_lead_list(df)
    crm = result["crm_ready_df"]

    assert crm["name"].tolist() == ["Piyush Kumar", "John Smith", "Jane Doe"]


def test_formatting_lowercases_emails():
    df = pd.DataFrame({
        "email": ["JOHN@EXAMPLE.COM", "Jane@Test.IO", "bob@corp.com"],
    })
    result = process_lead_list(df)
    crm = result["crm_ready_df"]

    assert crm["email"].tolist() == ["john@example.com", "jane@test.io", "bob@corp.com"]


def test_formatting_trims_whitespace():
    df = pd.DataFrame({
        "name": ["  Piyush Kumar  ", "  John Smith  ", "  Jane Doe  "],
        "email": ["a@b.com", "c@d.com", "e@f.com"],
    })
    result = process_lead_list(df)
    crm = result["crm_ready_df"]

    assert crm["name"].tolist() == ["Piyush Kumar", "John Smith", "Jane Doe"]


def test_formatting_report_populated():
    df = pd.DataFrame({
        "name": ["PIYUSH KUMAR", "JOHN SMITH", "JANE DOE"],
        "email": ["PIYUSH@MAIL.COM", "JOHN@MAIL.COM", "JANE@MAIL.COM"],
    })
    result = process_lead_list(df)
    report = result["report"]

    assert report["crm_formatting"]["name_fields_formatted"] >= 1
    assert report["crm_formatting"]["email_fields_normalized"] >= 1


# ─────────────────────────────────────────────
# Validation integration
# ─────────────────────────────────────────────


def test_validation_rejects_invalid_emails():
    df = pd.DataFrame({
        "email": ["john@example.com", "invalidemail", "jane@test.io"],
    })
    result = process_lead_list(df)

    assert len(result["rejected_df"]) == 1
    assert "DataForge_Rejection_Reason" in result["rejected_df"].columns


def test_validation_rejects_blank_emails():
    df = pd.DataFrame({
        "name": ["John", "Jane", "Bob", "Alice"],
        "email": ["john@example.com", None, "bob@example.com", "alice@test.io"],
    })
    result = process_lead_list(df)

    assert len(result["rejected_df"]) == 1


def test_validation_report_populated():
    df = pd.DataFrame({
        "email": ["john@example.com", "bad", None, "jane@test.io", "bob@corp.com"],
    })
    result = process_lead_list(df)
    val_report = result["report"]["validation"]

    assert val_report["total_rows"] == 5
    assert val_report["valid_rows"] == 3
    assert val_report["rejected_rows"] == 2


# ─────────────────────────────────────────────
# Deduplication integration
# ─────────────────────────────────────────────


def test_deduplication_removes_email_duplicates():
    df = pd.DataFrame({
        "name": ["John", "John Smith", "Jane Doe", "Bob Williams"],
        "email": ["john@example.com", "john@example.com", "jane@test.io", "bob@corp.com"],
        "phone": ["", "123456789", "555-1234", "555-5678"],
    })
    result = process_lead_list(df)

    # john@example.com appears twice → one deduplicated.
    assert len(result["crm_ready_df"]) == 3


def test_deduplication_keeps_most_complete():
    df = pd.DataFrame({
        "name": ["John", "John Smith", "Jane Doe", "Bob Williams"],
        "email": ["john@example.com", "john@example.com", "jane@test.io", "bob@corp.com"],
        "phone": ["", "123456789", "555-1234", "555-5678"],
    })
    result = process_lead_list(df)
    crm = result["crm_ready_df"]

    # The most complete John row (with phone) should be retained.
    john_rows = crm[crm["email"] == "john@example.com"]
    assert len(john_rows) == 1
    assert john_rows["phone"].iloc[0] == "123456789"


def test_deduplication_report_populated():
    df = pd.DataFrame({
        "name": ["John", "John"],
        "email": ["john@example.com", "john@example.com"],
    })
    result = process_lead_list(df)
    dedup_report = result["report"]["deduplication"]

    assert dedup_report["input_rows"] >= 1
    assert dedup_report["output_rows"] >= 1


# ─────────────────────────────────────────────
# Report generation
# ─────────────────────────────────────────────


def test_report_has_all_top_level_keys():
    df = pd.DataFrame({
        "email": ["a@b.com", "c@d.com"],
    })
    result = process_lead_list(df)
    report = result["report"]

    assert "input_rows" in report
    assert "output_rows" in report
    assert "rejected_rows" in report
    assert "semantic_types_detected" in report
    assert "crm_formatting" in report
    assert "validation" in report
    assert "deduplication" in report


def test_report_semantic_types_counted():
    df = pd.DataFrame({
        "email": ["a@b.com", "c@d.com", "e@f.com"],
        "name": ["Piyush Kumar", "Ankit Sharma", "Ravi Singh"],
    })
    result = process_lead_list(df)

    # Should detect at least email and full_name.
    assert result["report"]["semantic_types_detected"] >= 2


# ─────────────────────────────────────────────
# Config overrides
# ─────────────────────────────────────────────


def test_config_disable_formatting():
    df = pd.DataFrame({
        "name": ["PIYUSH KUMAR"],
        "email": ["PIYUSH@MAIL.COM"],
    })
    result = process_lead_list(df, config={"run_formatting": False})

    # Emails should NOT be lowercased.
    crm = result["crm_ready_df"]
    assert crm["email"].iloc[0] == "PIYUSH@MAIL.COM"
    assert result["report"]["crm_formatting"] == {}


def test_config_disable_validation():
    df = pd.DataFrame({
        "email": ["john@example.com", "invalidemail"],
    })
    result = process_lead_list(df, config={"run_validation": False})

    # Invalid emails should NOT be rejected.
    assert len(result["crm_ready_df"]) == 2
    assert len(result["rejected_df"]) == 0
    assert result["report"]["validation"] == {}


def test_config_disable_deduplication():
    df = pd.DataFrame({
        "name": ["John", "John"],
        "email": ["john@example.com", "john@example.com"],
    })
    result = process_lead_list(df, config={"run_deduplication": False})

    # Duplicates should NOT be removed (exact dup removal also off).
    # However, exact dup removal happens in dedup step, so both rows remain.
    assert len(result["crm_ready_df"]) == 2
    assert result["report"]["deduplication"] == {}


def test_config_disable_all_steps():
    df = pd.DataFrame({
        "name": ["PIYUSH"],
        "email": ["BAD_EMAIL"],
    })
    result = process_lead_list(
        df,
        config={
            "run_formatting": False,
            "run_validation": False,
            "run_deduplication": False,
        },
    )

    # Only semantic recognition runs. Data passes through unchanged.
    assert len(result["crm_ready_df"]) == 1
    assert result["crm_ready_df"]["name"].iloc[0] == "PIYUSH"
    assert result["crm_ready_df"]["email"].iloc[0] == "BAD_EMAIL"


# ─────────────────────────────────────────────
# Output integrity
# ─────────────────────────────────────────────


def test_rejected_rows_have_rejection_reason():
    df = pd.DataFrame({
        "email": ["john@example.com", "bad_email", None, "jane@test.io", "bob@corp.com"],
    })
    result = process_lead_list(df)
    rejected = result["rejected_df"]

    assert len(rejected) == 2
    assert "DataForge_Rejection_Reason" in rejected.columns
    assert all(rejected["DataForge_Rejection_Reason"] != "")


def test_crm_ready_rows_are_clean():
    df = pd.DataFrame({
        "name": ["  PIYUSH KUMAR  ", "  JOHN SMITH  "],
        "email": ["piyush@mail.com", "john@example.com"],
    })
    result = process_lead_list(df)
    crm = result["crm_ready_df"]

    # Names should be trimmed and title-cased.
    for name in crm["name"]:
        assert name == name.strip()
        assert name[0].isupper()


def test_existing_columns_preserved():
    df = pd.DataFrame({
        "name": ["Piyush Kumar"],
        "email": ["piyush@mail.com"],
        "company": ["Acme Inc"],
        "notes": ["VIP lead"],
    })
    result = process_lead_list(df)
    crm = result["crm_ready_df"]

    assert "company" in crm.columns
    assert "notes" in crm.columns
    assert crm["company"].iloc[0] == "Acme Inc"
    assert crm["notes"].iloc[0] == "VIP lead"


def test_original_df_not_mutated():
    df = pd.DataFrame({
        "name": ["  PIYUSH KUMAR  "],
        "email": ["PIYUSH@MAIL.COM"],
    })
    original_name = df["name"].iloc[0]
    original_email = df["email"].iloc[0]

    process_lead_list(df)

    # Original DataFrame should be untouched.
    assert df["name"].iloc[0] == original_name
    assert df["email"].iloc[0] == original_email


# ─────────────────────────────────────────────
# Mixed-quality dataset
# ─────────────────────────────────────────────


def test_mixed_quality_dataset():
    """Realistic messy lead list with all quality issues."""
    df = pd.DataFrame({
        "name": [
            "  PIYUSH KUMAR  ",
            "John",
            "  JOHN SMITH  ",
            "John S.",
            "  jane doe  ",
            "Bob",
        ],
        "email": [
            "PIYUSH@MAIL.COM",
            "invalidemail",
            "john@example.com",
            "john@example.com",
            "jane@test.io",
            None,
        ],
    })
    result = process_lead_list(df)

    crm = result["crm_ready_df"]
    rejected = result["rejected_df"]
    report = result["report"]

    # "invalidemail" and None should be rejected.
    assert len(rejected) >= 2

    # john@example.com appears twice → one should be deduplicated.
    email_counts = crm["email"].value_counts()
    assert email_counts.get("john@example.com", 0) <= 1

    # Report should show all phases ran.
    assert report["crm_formatting"] != {}
    assert report["validation"] != {}
    assert report["deduplication"] != {}

    # Input rows correct.
    assert report["input_rows"] == 6


# ─────────────────────────────────────────────
# Acceptance criteria (exact ticket scenario)
# ─────────────────────────────────────────────


def test_acceptance_criteria():
    """The exact acceptance criteria from the INT-001 ticket."""
    df = pd.DataFrame({
        "name": [
            " PIYUSH KUMAR ",
            "John",
            "John Smith",
            "John S.",
        ],
        "email": [
            "PIYUSH@MAIL.COM",
            "invalidemail",
            "john@example.com",
            "john@example.com",
        ],
    })
    result = process_lead_list(df)

    crm = result["crm_ready_df"]
    rejected = result["rejected_df"]
    report = result["report"]

    # Piyush should be CRM-ready with formatting applied.
    piyush_rows = crm[crm["email"] == "piyush@mail.com"]
    assert len(piyush_rows) == 1
    assert piyush_rows["name"].iloc[0] == "Piyush Kumar"

    # "invalidemail" should be rejected.
    assert len(rejected) >= 1

    # john@example.com duplicates should be deduplicated to 1.
    john_rows = crm[crm["email"] == "john@example.com"]
    assert len(john_rows) == 1

    # Report has formatting, validation, and deduplication counts.
    assert report["crm_formatting"] != {}
    assert report["validation"] != {}
    assert report["deduplication"] != {}
