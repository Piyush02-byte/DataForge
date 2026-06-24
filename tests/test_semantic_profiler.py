import pandas as pd

from src.core.semantic_profiler import (
    _is_company_name,
    _is_email,
    _is_full_name,
    _is_linkedin_profile,
    _is_phone_number,
    _is_url,
    semantic_profile_dataframe,
)


def _column_result(values, column="col"):
    df = pd.DataFrame({column: values})
    return semantic_profile_dataframe(df)["columns"][column]


def test_email_detection():
    result = _column_result(
        [
            "john@example.com",
            "jane.doe@company.co.uk",
            "a@b.io",
            "sales+west@example.org",
            "hello@test.net",
            "owner@site.in",
            "team@domain.dev",
            "x.y@sub.domain.com",
            "first.last@company.ai",
            "contact@business.co",
        ],
        "col1",
    )

    assert result["semantic_type"] == "email"
    assert result["confidence"] >= 0.85


def test_phone_detection_international():
    result = _column_result(
        [
            "+91 9876543210",
            "+1-555-123-4567",
            "020 7946 0958",
            "(555) 123-4567",
            "+44 20 7946 0958",
        ],
        "col2",
    )

    assert result["semantic_type"] == "phone_number"
    assert result["confidence"] >= 0.70


def test_full_name_detection():
    result = _column_result(
        [
            "Piyush Kumar",
            "Ankit Sharma",
            "John O'Brien",
            "Mary-Jane Watson",
            "Ravi Prakash Singh",
        ],
        "col3",
    )

    assert result["semantic_type"] == "full_name"
    assert result["confidence"] >= 0.75


def test_company_detection():
    result = _column_result(
        [
            "Infosys Ltd",
            "Google LLC",
            "Tata Motors Pvt Ltd",
            "Acme Corporation",
            "Globex Inc",
        ],
        "col4",
    )

    assert result["semantic_type"] == "company_name"
    assert result["confidence"] >= 0.70


def test_url_detection():
    result = _column_result(
        [
            "https://example.com",
            "http://blog.site.io/page",
            "www.company.org",
            "https://docs.python.org",
            "http://example.co.uk/path",
        ],
        "col5",
    )

    assert result["semantic_type"] == "url"
    assert result["confidence"] >= 0.80


def test_linkedin_detection():
    result = _column_result(
        [
            "https://linkedin.com/in/piyush",
            "https://www.linkedin.com/in/john",
            "http://linkedin.com/company/acme",
            "www.linkedin.com/in/jane",
        ],
        "col6",
    )

    assert result["semantic_type"] == "linkedin_profile"
    assert result["confidence"] >= 0.80


def test_first_name_with_header_hint():
    result = _column_result(["Piyush", "Ankit", "Ravi", "John"], "first_name")

    assert result["semantic_type"] == "first_name"
    assert result["confidence"] >= 0.70
    assert result["header_matched"] is True


def test_empty_column():
    result = _column_result([None, None, pd.NA], "empty")

    assert result["semantic_type"] == "unknown"
    assert result["confidence"] == 0.0
    assert "below minimum threshold" in result["reason"]


def test_mixed_type_column():
    result = _column_result(
        [
            "john@example.com",
            "jane@example.com",
            "Not an email",
            "555-1234",
            "owner@example.org",
        ],
        "mixed",
    )

    assert result["semantic_type"] in {"unknown", "email"}
    if result["semantic_type"] == "email":
        assert result["confidence"] >= 0.60


def test_numeric_column_ignored():
    result = _column_result([1, 2, 3, 4, 5], "numbers")

    assert result["semantic_type"] == "unknown"
    assert result["confidence"] == 0.0
    assert result["reason"] == "column dtype is int64; skipped semantic detection"


def test_gibberish_headers():
    df = pd.DataFrame(
        {
            "col_0": ["a@example.com", "b@example.com", "c@example.com"],
            "Unnamed: 1": ["Piyush Kumar", "Ankit Sharma", "Ravi Singh"],
            "xyz123": ["https://example.com", "www.site.org", "http://docs.io"],
        }
    )
    result = semantic_profile_dataframe(df)

    assert result["columns"]["col_0"]["semantic_type"] == "email"
    assert result["columns"]["Unnamed: 1"]["semantic_type"] == "full_name"
    assert result["columns"]["xyz123"]["semantic_type"] == "url"


def test_short_column():
    result = _column_result(["john@example.com", "jane@example.com"], "email")

    assert result["semantic_type"] == "unknown"
    assert result["confidence"] == 0.0
    assert "below minimum threshold of 3" in result["reason"]


def test_indian_phone_numbers():
    result = _column_result(
        ["+91 98765 43210", "09876543210", "91-9876543210"],
        "mobile",
    )

    assert result["semantic_type"] == "phone_number"


def test_company_vs_name_disambiguation():
    result = _column_result(
        ["Ravi Kumar", "Ankit Sharma", "Infosys Ltd", "Google LLC"],
        "mixed_names",
    )

    assert result["semantic_type"] == "unknown"


def test_linkedin_not_generic_url():
    result = _column_result(
        [
            "https://linkedin.com/in/piyush",
            "https://www.linkedin.com/in/john",
            "www.linkedin.com/company/acme",
        ],
        "url",
    )

    assert result["semantic_type"] == "linkedin_profile"


def test_reason_field_present():
    result = semantic_profile_dataframe(pd.DataFrame({"email": ["a@b.io", "c@d.io", "e@f.io"]}))

    assert all(col["reason"] for col in result["columns"].values())


def test_reason_format_on_match():
    result = _column_result(["a@b.io", "c@d.io", "e@f.io"], "email")

    assert "3/3" in result["reason"]


def test_reason_on_skip():
    result = _column_result([1, 2, 3], "numbers")

    assert "skipped semantic detection" in result["reason"]


def test_detector_field_present():
    result = semantic_profile_dataframe(
        pd.DataFrame(
            {
                "email": ["a@b.io", "c@d.io", "e@f.io"],
                "numbers": [1, 2, 3],
            }
        )
    )

    assert all(isinstance(col["detector"], str) and col["detector"] for col in result["columns"].values())


def test_full_dataframe_profiling():
    df = pd.DataFrame(
        {
            "emails": ["a@b.io", "c@d.io", "e@f.io"],
            "names": ["Piyush Kumar", "Ankit Sharma", "Ravi Singh"],
            "phones": ["+91 9876543210", "(555) 123-4567", "+44 20 7946 0958"],
            "companies": ["Infosys Ltd", "Google LLC", "Acme Inc"],
            "random_numbers": [1, 2, 3],
        }
    )
    result = semantic_profile_dataframe(df)

    assert result["detected_types_summary"]["email"] == ["emails"]
    assert result["detected_types_summary"]["full_name"] == ["names"]
    assert result["detected_types_summary"]["phone_number"] == ["phones"]
    assert result["detected_types_summary"]["company_name"] == ["companies"]
    assert result["detected_types_summary"]["unknown"] == ["random_numbers"]


def test_config_override():
    result = _column_result(
        ["a@b.io", "c@d.io", "not-email", "also-not-email", "still-not-email"],
        "email",
    )
    strict = semantic_profile_dataframe(
        pd.DataFrame({"email": ["a@b.io", "c@d.io", "not-email", "also-not-email", "still-not-email"]}),
        config={"confidence_threshold": 0.90},
    )["columns"]["email"]

    assert result["semantic_type"] == "email"
    assert strict["semantic_type"] == "unknown"


def test_detectors_are_independently_testable():
    assert _is_email("john@example.com")
    assert _is_phone_number("+91 9876543210")
    assert _is_url("https://example.com")
    assert _is_linkedin_profile("https://linkedin.com/in/piyush")
    assert _is_full_name("Piyush Kumar")
    assert _is_company_name("Infosys Ltd")


# ─────────────────────────────────────────────
# v1.2 Scoring Logic Tests
# ─────────────────────────────────────────────


def test_highest_confidence_wins_over_priority():
    """url detector should win over linkedin_profile when url has higher confidence.

    linkedin_profile has higher priority (index 0) but only matches a few values.
    url has lower priority (index 3) but matches almost all values.
    The highest-confidence detector must win, regardless of priority order.
    """
    values = [
        "https://example.com",
        "https://docs.python.org",
        "http://blog.site.io/page",
        "www.company.org",
        "http://example.co.uk/path",
        "https://google.com",
        "https://github.com/piyush",
        "http://stackoverflow.com",
        "https://linkedin.com/in/piyush",  # only 1 LinkedIn URL out of 10
        "www.reddit.com",
    ]
    result = _column_result(values, "links")

    # url detector should score ~1.0 (all values are URLs)
    # linkedin_profile detector should score ~0.1 (only 1/10 is LinkedIn)
    assert result["semantic_type"] == "url", (
        f"Expected 'url' but got '{result['semantic_type']}' "
        f"with confidence {result['confidence']}"
    )
    assert result["confidence"] >= 0.80


def test_tiebreaker_uses_priority_order():
    """When two detectors have identical confidence, priority order breaks the tie.

    All values are LinkedIn URLs, so both linkedin_profile and url detectors
    will match 100% of values. With identical match_ratio and no header boost,
    their confidence will be equal. linkedin_profile has higher priority
    (lower index) and should win.
    """
    values = [
        "https://linkedin.com/in/alice",
        "https://linkedin.com/in/bob",
        "https://linkedin.com/in/carol",
        "https://linkedin.com/in/dave",
        "https://linkedin.com/in/eve",
    ]
    result = _column_result(values, "links")

    # Both linkedin_profile and url match 100%.
    # linkedin_profile has priority index 0, url has priority index 3.
    # Tiebreaker should pick linkedin_profile.
    assert result["semantic_type"] == "linkedin_profile", (
        f"Expected 'linkedin_profile' but got '{result['semantic_type']}' "
        f"with confidence {result['confidence']}"
    )


def test_all_detectors_evaluated():
    """LinkedIn URLs should be classified as linkedin_profile because it scores
    highest — not because it is evaluated first.

    This test verifies that the evaluate-all strategy correctly identifies
    linkedin_profile as the best match for a column of LinkedIn URLs, and that
    the result is driven by confidence scoring rather than evaluation order.
    """
    values = [
        "https://linkedin.com/in/piyush",
        "https://www.linkedin.com/in/john",
        "https://linkedin.com/company/acme",
        "www.linkedin.com/in/jane",
        "https://linkedin.com/in/ravi",
    ]
    result = _column_result(values, "profiles")

    assert result["semantic_type"] == "linkedin_profile"
    # Confidence should be high since all values match linkedin_profile pattern
    assert result["confidence"] >= 0.80
    assert result["detector"] == "regex_v1"

