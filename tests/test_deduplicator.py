import pandas as pd
import numpy as np

from src.core.deduplicator import deduplicate_leads, _completeness_score
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
# Rule 1: Exact duplicate removal
# ─────────────────────────────────────────────


def test_exact_duplicate_removal():
    df = pd.DataFrame({
        "name": ["John", "John", "Jane"],
        "email": ["john@example.com", "john@example.com", "jane@example.com"],
    })
    profile = _make_manual_profile({"name": "full_name", "email": "email"})
    result, report = deduplicate_leads(df, profile)

    assert len(result) == 2
    assert report["exact_duplicates_removed"] == 1


def test_exact_duplicate_keeps_first():
    df = pd.DataFrame({
        "name": ["First", "First", "First"],
        "email": ["a@b.com", "a@b.com", "a@b.com"],
    })
    profile = _make_manual_profile({"name": "full_name", "email": "email"})
    result, _ = deduplicate_leads(df, profile)

    assert len(result) == 1
    assert result["name"].iloc[0] == "First"


def test_no_exact_duplicates():
    df = pd.DataFrame({
        "name": ["John", "Jane", "Bob"],
        "email": ["a@b.com", "c@d.com", "e@f.com"],
    })
    profile = _make_manual_profile({"name": "full_name", "email": "email"})
    result, report = deduplicate_leads(df, profile)

    assert len(result) == 3
    assert report["exact_duplicates_removed"] == 0


def test_exact_duplicate_multiple_groups():
    df = pd.DataFrame({
        "name": ["A", "A", "B", "B", "C"],
        "email": ["a@a.com", "a@a.com", "b@b.com", "b@b.com", "c@c.com"],
    })
    profile = _make_manual_profile({"name": "full_name", "email": "email"})
    result, report = deduplicate_leads(df, profile)

    assert len(result) == 3
    assert report["exact_duplicates_removed"] == 2


# ─────────────────────────────────────────────
# Rule 2: Email-based deduplication
# ─────────────────────────────────────────────


def test_email_duplicate_removal():
    df = pd.DataFrame({
        "name": ["John", "John Smith"],
        "email": ["john@example.com", "john@example.com"],
        "phone": ["", "123456789"],
    })
    profile = _make_manual_profile({"name": "full_name", "email": "email", "phone": "phone_number"})
    result, report = deduplicate_leads(df, profile)

    assert len(result) == 1
    assert report["email_duplicates_removed"] == 1


def test_email_duplicate_different_names():
    df = pd.DataFrame({
        "name": ["John", "Johnny"],
        "email": ["john@example.com", "john@example.com"],
    })
    profile = _make_manual_profile({"name": "full_name", "email": "email"})
    result, report = deduplicate_leads(df, profile)

    assert len(result) == 1
    assert report["email_duplicates_removed"] == 1


def test_multiple_email_duplicate_groups():
    df = pd.DataFrame({
        "name": ["A", "A2", "B", "B2", "C"],
        "email": ["a@x.com", "a@x.com", "b@x.com", "b@x.com", "c@x.com"],
    })
    profile = _make_manual_profile({"name": "full_name", "email": "email"})
    result, report = deduplicate_leads(df, profile)

    assert len(result) == 3
    assert report["email_duplicates_removed"] == 2


# ─────────────────────────────────────────────
# Rule 3: Most complete record retained
# ─────────────────────────────────────────────


def test_most_complete_row_retained():
    df = pd.DataFrame({
        "name": ["John", "John Smith"],
        "email": ["john@example.com", "john@example.com"],
        "phone": ["", "123456789"],
    })
    profile = _make_manual_profile({"name": "full_name", "email": "email", "phone": "phone_number"})
    result, _ = deduplicate_leads(df, profile)

    assert len(result) == 1
    # Row B has more complete data (name + email + phone vs name + email).
    assert result["name"].iloc[0] == "John Smith"
    assert result["phone"].iloc[0] == "123456789"


def test_most_complete_row_with_nulls():
    df = pd.DataFrame({
        "name": ["John", "John Smith"],
        "email": ["john@example.com", "john@example.com"],
        "phone": [None, "+91 9876543210"],
        "company": [None, "Acme Inc"],
    })
    profile = _make_manual_profile({
        "name": "full_name", "email": "email",
        "phone": "phone_number", "company": "company_name",
    })
    result, _ = deduplicate_leads(df, profile)

    assert len(result) == 1
    assert result["name"].iloc[0] == "John Smith"
    assert result["company"].iloc[0] == "Acme Inc"


def test_tied_completeness_keeps_first():
    df = pd.DataFrame({
        "name": ["First Row", "Second Row"],
        "email": ["same@example.com", "same@example.com"],
    })
    profile = _make_manual_profile({"name": "full_name", "email": "email"})
    result, _ = deduplicate_leads(df, profile)

    assert len(result) == 1
    # Equal completeness → first occurrence wins.
    assert result["name"].iloc[0] == "First Row"


def test_completeness_score_counts_correctly():
    row_sparse = pd.Series({"name": "John", "email": "john@example.com", "phone": "", "company": None})
    row_full = pd.Series({"name": "John", "email": "john@example.com", "phone": "123", "company": "Acme"})

    assert _completeness_score(row_sparse) == 2
    assert _completeness_score(row_full) == 4


def test_completeness_score_nan():
    row = pd.Series({"a": np.nan, "b": None, "c": "", "d": "value"})
    assert _completeness_score(row) == 1


# ─────────────────────────────────────────────
# Rule 4: Case-insensitive email matching
# ─────────────────────────────────────────────


def test_case_insensitive_email_dedup():
    df = pd.DataFrame({
        "name": ["John", "JOHN"],
        "email": ["JOHN@EXAMPLE.COM", "john@example.com"],
    })
    profile = _make_manual_profile({"name": "full_name", "email": "email"})
    result, report = deduplicate_leads(df, profile)

    assert len(result) == 1
    assert report["email_duplicates_removed"] == 1


def test_case_insensitive_mixed():
    df = pd.DataFrame({
        "email": ["John@Example.COM", "john@example.com", "JOHN@EXAMPLE.COM"],
    })
    profile = _make_manual_profile({"email": "email"})
    result, report = deduplicate_leads(df, profile)

    assert len(result) == 1
    assert report["email_duplicates_removed"] == 2


# ─────────────────────────────────────────────
# Rule 5: Blank emails ignored
# ─────────────────────────────────────────────


def test_blank_emails_not_deduped():
    df = pd.DataFrame({
        "name": ["John", "Jane", "Bob"],
        "email": [None, None, "bob@example.com"],
    })
    profile = _make_manual_profile({"name": "full_name", "email": "email"})
    result, report = deduplicate_leads(df, profile)

    # Two None emails should NOT be treated as duplicates.
    assert len(result) == 3
    assert report["email_duplicates_removed"] == 0


def test_empty_string_emails_not_deduped():
    df = pd.DataFrame({
        "name": ["John", "Jane"],
        "email": ["", ""],
    })
    profile = _make_manual_profile({"name": "full_name", "email": "email"})
    result, report = deduplicate_leads(df, profile)

    assert len(result) == 2
    assert report["email_duplicates_removed"] == 0


def test_nan_emails_not_deduped():
    df = pd.DataFrame({
        "name": ["John", "Jane"],
        "email": [np.nan, np.nan],
    })
    profile = _make_manual_profile({"name": "full_name", "email": "email"})
    result, report = deduplicate_leads(df, profile)

    assert len(result) == 2
    assert report["email_duplicates_removed"] == 0


# ─────────────────────────────────────────────
# Report accuracy
# ─────────────────────────────────────────────


def test_report_counts_accurate():
    df = pd.DataFrame({
        "name": ["A", "A", "B", "B2", "C"],
        "email": ["a@x.com", "a@x.com", "b@x.com", "b@x.com", "c@x.com"],
        "phone": ["", "", "111", "222", "333"],
    })
    profile = _make_manual_profile({"name": "full_name", "email": "email", "phone": "phone_number"})
    result, report = deduplicate_leads(df, profile)

    assert report["input_rows"] == 5
    # Row "A"/"A" are exact duplicates → 1 removed in step 1.
    # After exact dedup: [A, B, B2, C] → B and B2 share email → 1 removed in step 2.
    assert report["exact_duplicates_removed"] == 1
    assert report["email_duplicates_removed"] == 1
    assert report["output_rows"] == 3
    assert report["rows_retained"] == 3


def test_report_zero_when_no_duplicates():
    df = pd.DataFrame({
        "email": ["a@b.com", "c@d.com"],
    })
    profile = _make_manual_profile({"email": "email"})
    _, report = deduplicate_leads(df, profile)

    assert report["exact_duplicates_removed"] == 0
    assert report["email_duplicates_removed"] == 0
    assert report["input_rows"] == 2
    assert report["output_rows"] == 2


# ─────────────────────────────────────────────
# Config overrides
# ─────────────────────────────────────────────


def test_config_disable_exact_duplicates():
    df = pd.DataFrame({
        "name": ["John", "John"],
        "email": ["john@example.com", "john@example.com"],
    })
    profile = _make_manual_profile({"name": "full_name", "email": "email"})
    result, report = deduplicate_leads(
        df, profile, config={"remove_exact_duplicates": False}
    )

    # Exact dedup is off, but email dedup is still on → still removes 1.
    assert report["exact_duplicates_removed"] == 0
    assert report["email_duplicates_removed"] == 1
    assert len(result) == 1


def test_config_disable_email_duplicates():
    df = pd.DataFrame({
        "name": ["John", "John Smith"],
        "email": ["john@example.com", "john@example.com"],
    })
    profile = _make_manual_profile({"name": "full_name", "email": "email"})
    result, report = deduplicate_leads(
        df, profile, config={"remove_email_duplicates": False}
    )

    # Email dedup is off → both rows remain (not exact duplicates).
    assert len(result) == 2
    assert report["email_duplicates_removed"] == 0
    assert report["exact_duplicates_removed"] == 0


def test_config_disable_both():
    df = pd.DataFrame({
        "name": ["John", "John"],
        "email": ["john@example.com", "john@example.com"],
    })
    profile = _make_manual_profile({"name": "full_name", "email": "email"})
    result, report = deduplicate_leads(
        df, profile,
        config={"remove_exact_duplicates": False, "remove_email_duplicates": False},
    )

    assert len(result) == 2
    assert report["exact_duplicates_removed"] == 0
    assert report["email_duplicates_removed"] == 0


# ─────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────


def test_empty_dataframe():
    df = pd.DataFrame({"email": pd.Series([], dtype="object")})
    profile = _make_manual_profile({"email": "email"})
    result, report = deduplicate_leads(df, profile)

    assert len(result) == 0
    assert report["input_rows"] == 0
    assert report["output_rows"] == 0


def test_single_row():
    df = pd.DataFrame({"email": ["john@example.com"]})
    profile = _make_manual_profile({"email": "email"})
    result, report = deduplicate_leads(df, profile)

    assert len(result) == 1
    assert report["exact_duplicates_removed"] == 0
    assert report["email_duplicates_removed"] == 0


def test_no_email_columns():
    df = pd.DataFrame({
        "name": ["John", "John", "Jane"],
        "phone": ["111", "111", "222"],
    })
    profile = _make_manual_profile({"name": "full_name", "phone": "phone_number"})
    result, report = deduplicate_leads(df, profile)

    # Exact dedup still works; email dedup has nothing to do.
    assert len(result) == 2  # first two rows are exact dups
    assert report["exact_duplicates_removed"] == 1
    assert report["email_duplicates_removed"] == 0


def test_row_order_preserved():
    df = pd.DataFrame({
        "name": ["Charlie", "Alpha", "Charlie", "Bravo"],
        "email": ["c@x.com", "a@x.com", "c@x.com", "b@x.com"],
    })
    profile = _make_manual_profile({"name": "full_name", "email": "email"})
    result, _ = deduplicate_leads(df, profile)

    # After removing exact duplicate of Charlie, order should be: Charlie, Alpha, Bravo.
    names = result["name"].tolist()
    assert names == ["Charlie", "Alpha", "Bravo"]


def test_all_columns_preserved():
    df = pd.DataFrame({
        "name": ["John", "John Smith"],
        "email": ["john@example.com", "john@example.com"],
        "phone": ["", "123"],
        "company": ["", "Acme"],
    })
    profile = _make_manual_profile({
        "name": "full_name", "email": "email",
        "phone": "phone_number", "company": "company_name",
    })
    result, _ = deduplicate_leads(df, profile)

    assert "name" in result.columns
    assert "email" in result.columns
    assert "phone" in result.columns
    assert "company" in result.columns


def test_non_email_columns_not_used_for_dedup():
    """Different names but same email → still deduplicated.
    This verifies only email columns drive email dedup, not name columns."""
    df = pd.DataFrame({
        "name": ["John Smith", "Jonathan Smith"],
        "email": ["john@example.com", "john@example.com"],
    })
    profile = _make_manual_profile({"name": "full_name", "email": "email"})
    result, report = deduplicate_leads(df, profile)

    assert len(result) == 1
    assert report["email_duplicates_removed"] == 1


# ─────────────────────────────────────────────
# Integration with real semantic profiler
# ─────────────────────────────────────────────


def test_integration_with_real_semantic_profiler():
    df = pd.DataFrame({
        "email": [
            "john@example.com",
            "john@example.com",
            "jane@example.com",
            "jane@example.com",
            "bob@example.com",
        ],
        "name": [
            "John",
            "John Smith",
            "Jane",
            "Jane Doe",
            "Bob Williams",
        ],
    })
    profile = semantic_profile_dataframe(df)
    result, report = deduplicate_leads(df, profile)

    assert report["input_rows"] == 5
    assert report["output_rows"] == 3
    assert result["email"].tolist() == [
        "john@example.com", "jane@example.com", "bob@example.com"
    ]


# ─────────────────────────────────────────────
# Acceptance criteria (exact ticket scenario)
# ─────────────────────────────────────────────


def test_acceptance_criteria():
    """The exact acceptance criteria from the DF-004 ticket."""
    df = pd.DataFrame({
        "name": ["John", "John Smith"],
        "email": ["john@example.com", "john@example.com"],
        "phone": ["", "123456789"],
    })
    profile = _make_manual_profile({"name": "full_name", "email": "email", "phone": "phone_number"})
    result, report = deduplicate_leads(df, profile)

    assert len(result) == 1
    assert result["name"].iloc[0] == "John Smith"
    assert result["email"].iloc[0] == "john@example.com"
    assert result["phone"].iloc[0] == "123456789"
    assert report["email_duplicates_removed"] == 1


# ─────────────────────────────────────────────
# Three or more duplicates
# ─────────────────────────────────────────────


def test_three_duplicates_keeps_most_complete():
    df = pd.DataFrame({
        "name": ["J", "John", "John Smith"],
        "email": ["john@x.com", "john@x.com", "john@x.com"],
        "phone": ["", "", "123"],
    })
    profile = _make_manual_profile({"name": "full_name", "email": "email", "phone": "phone_number"})
    result, report = deduplicate_leads(df, profile)

    assert len(result) == 1
    assert result["name"].iloc[0] == "John Smith"
    assert result["phone"].iloc[0] == "123"
    assert report["email_duplicates_removed"] == 2


def test_mixed_blanks_and_duplicates():
    df = pd.DataFrame({
        "name": ["John", "John Smith", "Jane", "Bob"],
        "email": ["john@x.com", "john@x.com", None, None],
        "phone": ["", "123", "", "456"],
    })
    profile = _make_manual_profile({"name": "full_name", "email": "email", "phone": "phone_number"})
    result, report = deduplicate_leads(df, profile)

    # John/John Smith are email dups → keep John Smith (more complete).
    # Two None emails are NOT dups → both kept.
    assert len(result) == 3
    assert report["email_duplicates_removed"] == 1
