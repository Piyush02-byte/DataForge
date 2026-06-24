# DF-001 v1.1: Semantic Column Recognition Engine

| Field | Value |
|:---|:---|
| **Ticket** | DF-001 |
| **Version** | v1.1 |
| **Type** | Feature — New Module |
| **Priority** | P0 (MVP Blocker) |
| **Sprint** | Phase 1 — Week 1 |
| **Assignee** | Codex |
| **Reviewer** | ChatGPT (Architecture), Piyush (Validation) |
| **Status** | Ready for Development |

---

## Summary

Create `src/core/semantic_profiler.py` — a module that inspects the **actual cell values** of each column in a DataFrame and classifies it into a semantic type (`email`, `phone_number`, `full_name`, `first_name`, `last_name`, `company_name`, `url`, `linkedin_profile`, or `unknown`).

This module is the intelligence layer that all downstream MVP features depend on. Without it, the CRM Formatter (DF-002), Email Validator (DF-003), and Smart Deduplicator (DF-004) cannot know *which* columns to operate on.

---

## Goal

> Given any CSV with arbitrary column headers (or no meaningful headers), automatically detect what kind of real-world data each column contains, using the values themselves — not just the header text.

---

## Implementation Priorities

All engineering decisions in this ticket must follow this priority order:

1. **Correctness** — The detectors must return accurate results for the defined test cases.
2. **Readability** — The code must be understandable by a new contributor without explanation.
3. **Testability** — Every detector must be independently testable as a pure function.
4. **Extensibility** — Adding a new semantic type in the future should require adding one detector function and one entry in the cascade, nothing more.
5. **Performance** — Last priority. Avoid premature optimization.

> [!CAUTION]
> Do **not** introduce frameworks, abstract base classes, registries, plugin systems, metaclasses, or unnecessary class hierarchies. Implement the simplest solution that satisfies all acceptance criteria.

---

## Files

| Action | Path |
|:---|:---|
| **CREATE** | [src/core/semantic_profiler.py](file:///C:/Users/piyus/csv-data-quality-pipeline/src/core/semantic_profiler.py) |
| **CREATE** | [tests/test_semantic_profiler.py](file:///C:/Users/piyus/csv-data-quality-pipeline/tests/test_semantic_profiler.py) |
| **CREATE** | [tests/__init__.py](file:///C:/Users/piyus/csv-data-quality-pipeline/tests/__init__.py) |
| **MODIFY** | [src/core/__init__.py](file:///C:/Users/piyus/csv-data-quality-pipeline/src/core/__init__.py) — add `semantic_profile_dataframe` to public exports |

> [!IMPORTANT]
> **No shared config file modifications.** Do **not** modify `src/config.py` or `src/utils/config.py`. The Semantic Profiler is the first MVP module. Shared configuration architecture should not be introduced until multiple modules depend on it. All config lives inside `semantic_profiler.py` itself (see Config section below).

> [!IMPORTANT]
> Do **not** modify `pipeline.py` or `cli.py` in this ticket. Pipeline integration will be a separate ticket (DF-005) after all four engine modules are built and individually tested.

---

## Technical Design

### 1. Self-Contained Configuration

Define defaults inside `semantic_profiler.py`:

```python
DEFAULT_SEMANTIC_CONFIG = {
    "sample_size": 100,                # max values to sample per column
    "min_non_null_for_detection": 3,   # skip detection if fewer non-null values
    "confidence_threshold": 0.60,      # minimum confidence to assign a type
    "header_boost": 0.20,              # confidence bonus when header alias matches
}
```

The public function signature:

```python
def semantic_profile_dataframe(df: pd.DataFrame, config: dict | None = None) -> dict:
```

Config merging behavior:

```python
cfg = {**DEFAULT_SEMANTIC_CONFIG, **(config or {})}
```

User-supplied keys override defaults. Missing keys fall back to defaults. This is the full extent of config handling — no config classes, no validation, no schema enforcement.

---

### 2. Detection Strategy: Two-Pass Approach

**Pass 1 — Header Hint (Low Weight)**

Check the column header string against known aliases. This gives a *hint*, not a decision.

```python
HEADER_ALIASES = {
    "email":            ["email", "e-mail", "email_address", "emailaddress", "mail"],
    "phone_number":     ["phone", "mobile", "tel", "telephone", "phone_number", "contact_number"],
    "first_name":       ["first_name", "firstname", "first", "fname", "given_name"],
    "last_name":        ["last_name", "lastname", "last", "lname", "surname", "family_name"],
    "full_name":        ["name", "full_name", "fullname", "contact_name", "person"],
    "company_name":     ["company", "company_name", "organization", "organisation", "org", "employer", "firm"],
    "url":              ["url", "website", "web", "link", "homepage", "site"],
    "linkedin_profile": ["linkedin", "linkedin_url", "linkedin_profile"],
}
```

Matching rule: `column_header.strip().lower().replace(" ", "_")` checked against alias lists. A match contributes the configured `header_boost` (default `+0.20`) to the confidence score.

**Pass 2 — Value Sampling (High Weight)**

Sample up to `N` non-null values from the column (default `N = 100`, configurable). Run each value through a cascade of detector functions. The type whose detector matches the highest fraction of sampled values wins.

---

### 3. Detector Functions

Each detector is a **pure function** with the signature `(value: str) -> bool`. Each detector must be independently importable and testable.

```text
┌──────────────────┬─────────────────────────────────────────────────────────────┐
│ Semantic Type    │ Detection Rule                                              │
├──────────────────┼─────────────────────────────────────────────────────────────┤
│ email            │ RFC-lite regex:                                              │
│                  │ ^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$        │
│                  │                                                             │
│ phone_number     │ Digits-only after stripping +, -, (, ), spaces, dots.       │
│                  │ Cleaned digit count must be between 7 and 15 (inclusive).   │
│                  │ Original value must start with + or digit.                  │
│                  │                                                             │
│ url              │ Starts with http:// or https:// or www.                     │
│                  │ Contains at least one dot after the protocol.               │
│                  │                                                             │
│ linkedin_profile │ Matches url rule AND contains "linkedin.com" (case-insens.) │
│                  │ This is checked BEFORE generic url so it takes priority.    │
│                  │                                                             │
│ full_name        │ 2-4 whitespace-separated tokens.                            │
│                  │ Each token is alpha-only (allowing hyphens and apostrophes).│
│                  │ Total length between 3 and 60 characters.                  │
│                  │ Not a known company suffix pattern (see company_name).      │
│                  │                                                             │
│ first_name       │ Single alpha token, 2-20 chars.                             │
│                  │ Distinguished from last_name by header hint only.           │
│                  │ If no header hint, classified as first_name by default.     │
│                  │                                                             │
│ last_name        │ Same value pattern as first_name.                           │
│                  │ Requires header hint to distinguish from first_name.        │
│                  │                                                             │
│ company_name     │ See "Company Detection Architecture" section below.         │
└──────────────────┴─────────────────────────────────────────────────────────────┘
```

**Detection Cascade Priority Order:**

Detectors are evaluated in this fixed order. The first type to exceed the confidence threshold wins. This ordering prevents misclassification (e.g., LinkedIn URLs being classified as generic URLs).

```text
1. linkedin_profile  (most specific URL)
2. email
3. phone_number
4. url                (generic, after linkedin is excluded)
5. full_name
6. first_name / last_name
7. company_name       (most ambiguous, evaluated last)
```

---

### 4. Company Detection Architecture

> [!WARNING]
> Company-name detection is inherently ambiguous. "Ravi Kumar" could be a person or a company. MVP accuracy is sufficient. Do **not** attempt to solve all company-name edge cases in this ticket.

**Architectural Requirement:** Company-name detection must be implemented as a single, isolated detector function (`_is_company_name(value: str) -> bool`). It must **not** have its logic scattered across other detector functions or the main profiling loop.

The detector must be replaceable in future iterations without touching any other code.

**MVP Detection Rule:**

```python
COMPANY_SUFFIXES = [
    "llc", "inc", "ltd", "corp", "gmbh", "pvt", "llp",
    "co.", "plc", "s.a.", "ag", "pte", "limited", "incorporated",
    "corporation", "pvt ltd", "pvt. ltd.", "private limited",
]

def _is_company_name(value: str) -> bool:
    """Detect company names by known legal suffixes."""
    lower = value.strip().lower()
    return any(lower.endswith(suffix) for suffix in COMPANY_SUFFIXES)
```

**Priority:** Maintainability over perfect detection. If a value like `"Google"` (no suffix) is not detected as a company, that is acceptable for MVP. False negatives are tolerable. False positives (classifying a person's name as a company) are not.

---

### 5. Confidence Scoring Algorithm

For each column, for each candidate semantic type:

```python
match_ratio = matched_samples / total_samples  # 0.0 to 1.0
header_boost = cfg["header_boost"] if header_alias_matched else 0.0
confidence = min(1.0, match_ratio + header_boost)
```

Classification rules:
- If `confidence >= cfg["confidence_threshold"]` → assign the semantic type.
- If `confidence < cfg["confidence_threshold"]` → assign `"unknown"`.
- If two types both exceed the threshold → the type with the higher priority in the cascade wins.

---

### 6. Sampling Strategy

```python
sample_size = min(len(non_null_values), cfg["sample_size"])
sampled = non_null_values.sample(n=sample_size, random_state=42)
```

- Use `random_state=42` for deterministic results across runs.
- Only sample from non-null, non-empty-string values.
- Strip whitespace from sampled values before passing to detectors.
- If a column has fewer than `cfg["min_non_null_for_detection"]` non-null values, skip detection and return `"unknown"` with `confidence = 0.0`.
- Only process columns with `object` or `string` dtype. Numeric, datetime, and boolean columns are automatically classified as `"unknown"`.

---

### 7. Return Schema

The public function `semantic_profile_dataframe(df, config=None)` must return:

```python
{
    "columns": {
        "email_column": {
            "semantic_type": "email",                                    # str
            "confidence": 0.94,                                          # float 0.0-1.0
            "reason": "94/100 sampled values matched email pattern",     # str (human-readable)
            "header_matched": True,                                      # bool
            "sample_size": 100,                                          # int
            "match_count": 94,                                           # int
            "detector": "regex_v1",                                      # str (detector identifier)
        },
        "name_column": {
            "semantic_type": "full_name",
            "confidence": 0.82,
            "reason": "41/50 sampled values matched full_name pattern",
            "header_matched": False,
            "sample_size": 50,
            "match_count": 41,
            "detector": "regex_v1",
        },
        "random_numbers": {
            "semantic_type": "unknown",
            "confidence": 0.0,
            "reason": "column dtype is numeric; skipped semantic detection",
            "header_matched": False,
            "sample_size": 0,
            "match_count": 0,
            "detector": "none",
        },
    },
    "detected_types_summary": {
        "email": ["email_column"],
        "full_name": ["name_column"],
        "unknown": ["random_numbers"],
    }
}
```

**Field definitions:**

| Field | Type | Description |
|:---|:---|:---|
| `semantic_type` | `str` | The detected type, or `"unknown"` |
| `confidence` | `float` | 0.0 to 1.0, including header boost |
| `reason` | `str` | Human-readable explanation of why this type was assigned. Format: `"{match_count}/{sample_size} sampled values matched {type} pattern"` or a specific skip reason |
| `header_matched` | `bool` | Whether the column header matched a known alias |
| `sample_size` | `int` | Number of values actually sampled |
| `match_count` | `int` | Number of sampled values that matched the winning detector |
| `detector` | `str` | Identifier of the detector that produced this result. Use `"regex_v1"` for all regex-based detectors in this version. Use `"none"` for skipped/unknown columns |

**Reason field examples:**

```text
"94/100 sampled values matched email pattern"
"41/50 sampled values matched full_name pattern; header boost applied"
"column dtype is numeric; skipped semantic detection"
"only 2 non-null values; below minimum threshold of 3"
"no detector exceeded confidence threshold of 0.60"
```

---

## Acceptance Criteria

- [ ] `semantic_profile_dataframe(df)` accepts a `pd.DataFrame` and returns the schema defined above.
- [ ] Detection works correctly even when column headers are nonsensical (e.g., `col1`, `col2`, `Unnamed: 0`).
- [ ] Email detection correctly identifies a column with 90%+ valid emails and assigns `"email"` with confidence ≥ 0.85.
- [ ] Phone detection handles international formats: `+91 9876543210`, `(555) 123-4567`, `+44 20 7946 0958`.
- [ ] `full_name` is distinguished from `company_name` (e.g., `"Piyush Kumar"` → name, `"Infosys Ltd"` → company).
- [ ] `linkedin_profile` is detected as its own type, NOT as generic `url`.
- [ ] Columns with fewer than 3 non-null values return `"unknown"` with `confidence = 0.0`.
- [ ] Every result includes a human-readable `reason` string.
- [ ] Every result includes a `detector` identifier string.
- [ ] Company detection logic lives in a single isolated function (`_is_company_name`), not scattered across the module.
- [ ] Config defaults are defined inside `semantic_profiler.py`. No modifications to `src/config.py` or `src/utils/config.py`.
- [ ] The module has **zero side effects**: no printing, no file I/O, no global state mutation.
- [ ] The module follows existing codebase conventions: returns structured dicts, accepts optional config dict, private helpers prefixed with `_`.
- [ ] All unit tests pass.

---

## Unit Test Requirements

Create [tests/test_semantic_profiler.py](file:///C:/Users/piyus/csv-data-quality-pipeline/tests/test_semantic_profiler.py) with the following test cases:

### Happy Path Tests

| Test Name | Input Column Values | Expected Type | Min Confidence |
|:---|:---|:---|:---|
| `test_email_detection` | `["john@example.com", "jane.doe@company.co.uk", "a@b.io", ...]` | `email` | 0.85 |
| `test_phone_detection_international` | `["+91 9876543210", "+1-555-123-4567", "020 7946 0958", ...]` | `phone_number` | 0.70 |
| `test_full_name_detection` | `["Piyush Kumar", "Ankit Sharma", "John O'Brien", ...]` | `full_name` | 0.75 |
| `test_company_detection` | `["Infosys Ltd", "Google LLC", "Tata Motors Pvt Ltd", ...]` | `company_name` | 0.70 |
| `test_url_detection` | `["https://example.com", "http://blog.site.io/page", ...]` | `url` | 0.80 |
| `test_linkedin_detection` | `["https://linkedin.com/in/piyush", "https://www.linkedin.com/in/john", ...]` | `linkedin_profile` | 0.80 |
| `test_first_name_with_header_hint` | Header: `"first_name"`, Values: `["Piyush", "Ankit", "Ravi", ...]` | `first_name` | 0.70 |

### Edge Case Tests

| Test Name | Scenario | Expected Behavior |
|:---|:---|:---|
| `test_empty_column` | Column is all `NaN` / `None` | Returns `"unknown"`, confidence `0.0`, reason explains skip |
| `test_mixed_type_column` | `["john@example.com", "Not an email", "555-1234", ...]` | Returns `"unknown"` or the dominant type if ≥ 60% match |
| `test_numeric_column_ignored` | Column of integers `[1, 2, 3, 4, 5]` | Returns `"unknown"`, reason: `"column dtype is numeric; skipped semantic detection"` |
| `test_gibberish_headers` | Headers: `["col_0", "Unnamed: 1", "xyz123"]` | Detection still works via value sampling |
| `test_short_column` | Only 2 non-null values | Returns `"unknown"`, confidence `0.0`, reason references threshold |
| `test_indian_phone_numbers` | `["+91 98765 43210", "09876543210", "91-9876543210"]` | Returns `"phone_number"` |
| `test_company_vs_name_disambiguation` | `["Ravi Kumar", "Infosys Ltd"]` mixed | Returns `"unknown"` (neither type reaches 60%) |
| `test_linkedin_not_generic_url` | All values are LinkedIn URLs | Returns `"linkedin_profile"`, NOT `"url"` |

### Explainability Tests

| Test Name | Scenario | Expected Behavior |
|:---|:---|:---|
| `test_reason_field_present` | Any valid DataFrame | Every column result has a non-empty `reason` string |
| `test_reason_format_on_match` | Column of emails | `reason` contains match count and sample size (e.g., `"94/100"`) |
| `test_reason_on_skip` | Numeric column | `reason` explains why detection was skipped |
| `test_detector_field_present` | Any valid DataFrame | Every column result has a `detector` string |

### Integration Smoke Test

| Test Name | Scenario | Expected Behavior |
|:---|:---|:---|
| `test_full_dataframe_profiling` | DataFrame with 5 columns: emails, names, phones, companies, random numbers | `detected_types_summary` correctly maps each column to its type |
| `test_config_override` | Pass custom `{"confidence_threshold": 0.90}` | Only high-confidence columns are classified; others fall to `"unknown"` |

---

## Conventions to Follow

These are patterns observed in the existing codebase that **must** be maintained:

1. **Return dicts, not classes.** Every public function in `src/core/` returns a plain `dict`. Follow this pattern.
2. **Config injection.** Accept an optional `config: dict | None = None` parameter. Merge with `DEFAULT_SEMANTIC_CONFIG` using `{**DEFAULT_SEMANTIC_CONFIG, **(config or {})}`. See [cleaner.py:L22](file:///C:/Users/piyus/csv-data-quality-pipeline/src/core/cleaner.py#L22) and [type_coercer.py:L19](file:///C:/Users/piyus/csv-data-quality-pipeline/src/core/type_coercer.py#L19) for the existing pattern.
3. **No side effects.** No `print()`, no file writes, no global mutations. See the docstring convention in [cleaner.py:L2-L12](file:///C:/Users/piyus/csv-data-quality-pipeline/src/core/cleaner.py#L2-L12).
4. **Module docstring.** Include a module-level docstring with `Responsibility:` section matching the style in [cleaner.py](file:///C:/Users/piyus/csv-data-quality-pipeline/src/core/cleaner.py) and [type_coercer.py](file:///C:/Users/piyus/csv-data-quality-pipeline/src/core/type_coercer.py).
5. **Internal helpers prefixed with `_`.** Public API functions are at the top, private helpers below a separator comment. See [type_coercer.py:L70-L72](file:///C:/Users/piyus/csv-data-quality-pipeline/src/core/type_coercer.py#L70-L72).

---

## Out of Scope

The following are explicitly **NOT** part of this ticket:

- Pipeline integration (DF-005)
- CRM formatting logic (DF-002)
- Email validation logic (DF-003)
- Deduplication logic (DF-004)
- Modifications to `src/config.py` or `src/utils/config.py`
- CLI changes
- Web app / server
- Any UI work
- Solving all company-name edge cases (MVP accuracy is sufficient)
- Abstract plugin/registry architectures

---

## Changelog from v1.0

| Change | What Changed | Why |
|:---|:---|:---|
| Config isolation | Removed `MODIFY src/config.py` and `MODIFY src/utils/config.py`. Config now lives inside `semantic_profiler.py` as `DEFAULT_SEMANTIC_CONFIG`. | Reduce coupling. First MVP module should not introduce shared config dependencies. |
| Explainability | Added `reason` field to every column result. | Debugging, future UI messaging, transparency. |
| Detector metadata | Added `detector` field (`"regex_v1"` or `"none"`) to every column result. | Future reporting and version tracking for detection logic. |
| Company isolation | Added architectural requirement that company detection must be a single isolated function. | Maintainability over perfect detection. Detector must be replaceable without touching other code. |
| Implementation priorities | Added explicit priority order: Correctness > Readability > Testability > Extensibility > Performance. | Prevent premature optimization and over-engineering. |
| New test cases | Added 4 explainability tests and 1 config override test. | Cover new `reason` and `detector` fields. |
