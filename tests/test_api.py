import io
import json
import zipfile

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from server import app


client = TestClient(app)


def _make_csv_bytes(df: pd.DataFrame) -> bytes:
    """Helper: convert a DataFrame to CSV bytes for upload."""
    return df.to_csv(index=False).encode("utf-8")


def _upload_csv(csv_bytes: bytes, filename: str = "leads.csv"):
    """Helper: POST a CSV file to /process and return the response."""
    return client.post(
        "/process",
        files={"file": (filename, io.BytesIO(csv_bytes), "text/csv")},
    )


def _extract_zip(response) -> dict[str, bytes]:
    """Helper: extract ZIP contents from a response into a dict."""
    zip_buffer = io.BytesIO(response.content)
    with zipfile.ZipFile(zip_buffer, "r") as zf:
        return {name: zf.read(name) for name in zf.namelist()}


# ─────────────────────────────────────────────
# Health endpoint
# ─────────────────────────────────────────────


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_endpoint_method_not_allowed():
    response = client.post("/health")
    assert response.status_code == 405


# ─────────────────────────────────────────────
# Successful CSV upload
# ─────────────────────────────────────────────


def test_successful_csv_upload():
    df = pd.DataFrame({
        "name": ["Piyush Kumar", "Ankit Sharma", "Ravi Singh"],
        "email": ["piyush@mail.com", "ankit@test.io", "ravi@corp.com"],
    })
    response = _upload_csv(_make_csv_bytes(df))
    assert response.status_code == 200


def test_successful_upload_returns_zip():
    df = pd.DataFrame({
        "name": ["Piyush Kumar", "Ankit Sharma", "Ravi Singh"],
        "email": ["piyush@mail.com", "ankit@test.io", "ravi@corp.com"],
    })
    response = _upload_csv(_make_csv_bytes(df))
    assert response.headers["content-type"] == "application/zip"


def test_successful_upload_content_disposition():
    df = pd.DataFrame({
        "name": ["Piyush Kumar", "Ankit Sharma", "Ravi Singh"],
        "email": ["piyush@mail.com", "ankit@test.io", "ravi@corp.com"],
    })
    response = _upload_csv(_make_csv_bytes(df))
    assert "dataforge_results.zip" in response.headers.get("content-disposition", "")


# ─────────────────────────────────────────────
# ZIP contents
# ─────────────────────────────────────────────


def test_zip_contains_crm_ready_csv():
    df = pd.DataFrame({
        "name": ["Piyush Kumar", "Ankit Sharma", "Ravi Singh"],
        "email": ["piyush@mail.com", "ankit@test.io", "ravi@corp.com"],
    })
    response = _upload_csv(_make_csv_bytes(df))
    contents = _extract_zip(response)

    assert "crm_ready.csv" in contents


def test_zip_contains_rejected_leads_csv():
    df = pd.DataFrame({
        "name": ["Piyush Kumar", "Ankit Sharma", "Ravi Singh"],
        "email": ["piyush@mail.com", "ankit@test.io", "ravi@corp.com"],
    })
    response = _upload_csv(_make_csv_bytes(df))
    contents = _extract_zip(response)

    assert "rejected_leads.csv" in contents


def test_zip_contains_report_json():
    df = pd.DataFrame({
        "name": ["Piyush Kumar", "Ankit Sharma", "Ravi Singh"],
        "email": ["piyush@mail.com", "ankit@test.io", "ravi@corp.com"],
    })
    response = _upload_csv(_make_csv_bytes(df))
    contents = _extract_zip(response)

    assert "report.json" in contents
    report = json.loads(contents["report.json"])
    assert "input_rows" in report
    assert "output_rows" in report


def test_zip_report_is_valid_json():
    df = pd.DataFrame({
        "name": ["Piyush Kumar", "Ankit Sharma", "Ravi Singh"],
        "email": ["piyush@mail.com", "ankit@test.io", "ravi@corp.com"],
    })
    response = _upload_csv(_make_csv_bytes(df))
    contents = _extract_zip(response)

    report = json.loads(contents["report.json"])
    assert isinstance(report, dict)
    assert report["input_rows"] == 3


def test_zip_crm_ready_is_valid_csv():
    df = pd.DataFrame({
        "name": ["Piyush Kumar", "Ankit Sharma", "Ravi Singh"],
        "email": ["piyush@mail.com", "ankit@test.io", "ravi@corp.com"],
    })
    response = _upload_csv(_make_csv_bytes(df))
    contents = _extract_zip(response)

    crm_df = pd.read_csv(io.BytesIO(contents["crm_ready.csv"]))
    assert len(crm_df) >= 1
    assert "email" in crm_df.columns


# ─────────────────────────────────────────────
# Error handling
# ─────────────────────────────────────────────


def test_missing_file():
    response = client.post("/process")
    assert response.status_code == 422  # FastAPI validation error


def test_invalid_extension():
    response = client.post(
        "/process",
        files={"file": ("data.xlsx", io.BytesIO(b"fake data"), "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "CSV" in response.json()["detail"]


def test_invalid_extension_txt():
    response = client.post(
        "/process",
        files={"file": ("data.txt", io.BytesIO(b"some text"), "text/plain")},
    )
    assert response.status_code == 400
    assert "CSV" in response.json()["detail"]


def test_empty_csv():
    # CSV with headers but no data rows.
    csv_bytes = b"name,email\n"
    response = _upload_csv(csv_bytes)
    assert response.status_code == 400
    assert "no rows" in response.json()["detail"].lower()


def test_malformed_csv():
    csv_bytes = b"\x00\x01\x02\x03\x04"
    response = _upload_csv(csv_bytes)
    assert response.status_code == 400


# ─────────────────────────────────────────────
# Response headers
# ─────────────────────────────────────────────


def test_response_headers():
    df = pd.DataFrame({
        "email": ["a@b.com", "c@d.com", "e@f.com"],
    })
    response = _upload_csv(_make_csv_bytes(df))

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "content-disposition" in response.headers


# ─────────────────────────────────────────────
# Small valid dataset
# ─────────────────────────────────────────────


def test_small_valid_dataset():
    df = pd.DataFrame({
        "email": ["a@b.com", "c@d.com", "e@f.com"],
        "name": ["Alpha Beta", "Charlie Delta", "Echo Foxtrot"],
    })
    response = _upload_csv(_make_csv_bytes(df))
    contents = _extract_zip(response)

    crm_df = pd.read_csv(io.BytesIO(contents["crm_ready.csv"]))
    assert len(crm_df) == 3


# ─────────────────────────────────────────────
# Dataset with rejected leads
# ─────────────────────────────────────────────


def test_dataset_with_rejected_leads():
    df = pd.DataFrame({
        "name": ["John Smith", "Jane Doe", "Bad Lead", "Another Bad", "Good One"],
        "email": ["john@example.com", "jane@test.io", "invalidemail", "also_bad", "good@test.com"],
    })
    response = _upload_csv(_make_csv_bytes(df))
    contents = _extract_zip(response)

    crm_df = pd.read_csv(io.BytesIO(contents["crm_ready.csv"]))
    rejected_df = pd.read_csv(io.BytesIO(contents["rejected_leads.csv"]))
    report = json.loads(contents["report.json"])

    assert len(crm_df) >= 3
    assert len(rejected_df) >= 2
    assert report["rejected_rows"] >= 2


def test_rejected_leads_have_reason_column():
    df = pd.DataFrame({
        "name": ["John Smith", "Jane Doe", "Bad Lead", "Another Bad", "Good One"],
        "email": ["john@example.com", "jane@test.io", "invalidemail", "also_bad", "good@test.com"],
    })
    response = _upload_csv(_make_csv_bytes(df))
    contents = _extract_zip(response)

    rejected_df = pd.read_csv(io.BytesIO(contents["rejected_leads.csv"]))
    assert "DataForge_Rejection_Reason" in rejected_df.columns


# ─────────────────────────────────────────────
# Dataset with duplicates
# ─────────────────────────────────────────────


def test_dataset_with_duplicates():
    df = pd.DataFrame({
        "name": ["John", "John Smith", "Jane Doe", "Bob Williams", "Alice Brown"],
        "email": [
            "john@example.com",
            "john@example.com",
            "jane@test.io",
            "bob@corp.com",
            "alice@mail.com",
        ],
        "phone": ["", "123456789", "555-1234", "555-5678", "555-9999"],
    })
    response = _upload_csv(_make_csv_bytes(df))
    contents = _extract_zip(response)

    crm_df = pd.read_csv(io.BytesIO(contents["crm_ready.csv"]))
    report = json.loads(contents["report.json"])

    # john@example.com duplicate should be deduplicated to 1.
    john_rows = crm_df[crm_df["email"] == "john@example.com"]
    assert len(john_rows) == 1

    # Deduplication report should reflect removal.
    assert report["deduplication"]["email_duplicates_removed"] >= 1


# ─────────────────────────────────────────────
# Formatting through API
# ─────────────────────────────────────────────


def test_names_formatted_through_api():
    df = pd.DataFrame({
        "name": ["  PIYUSH KUMAR  ", "  john smith  ", "  JANE DOE  "],
        "email": ["piyush@mail.com", "john@test.io", "jane@corp.com"],
    })
    response = _upload_csv(_make_csv_bytes(df))
    contents = _extract_zip(response)

    crm_df = pd.read_csv(io.BytesIO(contents["crm_ready.csv"]))
    names = crm_df["name"].tolist()

    assert "Piyush Kumar" in names
    assert "John Smith" in names
    assert "Jane Doe" in names


def test_emails_lowercased_through_api():
    df = pd.DataFrame({
        "email": ["JOHN@EXAMPLE.COM", "Jane@Test.IO", "bob@corp.com"],
    })
    response = _upload_csv(_make_csv_bytes(df))
    contents = _extract_zip(response)

    crm_df = pd.read_csv(io.BytesIO(contents["crm_ready.csv"]))
    emails = crm_df["email"].tolist()

    assert all(e == e.lower() for e in emails)


# ─────────────────────────────────────────────
# No disk files created
# ─────────────────────────────────────────────


def test_no_disk_files_created(tmp_path):
    """Verify the endpoint doesn't create files in the working directory."""
    import os

    cwd_files_before = set(os.listdir("."))

    df = pd.DataFrame({
        "email": ["a@b.com", "c@d.com", "e@f.com"],
    })
    _upload_csv(_make_csv_bytes(df))

    cwd_files_after = set(os.listdir("."))
    new_files = cwd_files_after - cwd_files_before

    # Filter out __pycache__ and .pytest_cache which pytest may create.
    meaningful_new_files = {
        f for f in new_files
        if not f.startswith(".") and not f.startswith("__")
    }
    assert len(meaningful_new_files) == 0, f"Unexpected files created: {meaningful_new_files}"
