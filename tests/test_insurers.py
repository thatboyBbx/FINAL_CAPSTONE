"""
Tests for the insurers API endpoints.
"""
import io
import pytest
from fastapi.testclient import TestClient


def test_csv_import_no_file(authenticated_client: TestClient):
    """POST /insurers/import-csv with no file — expect 422."""
    resp = authenticated_client.post("/insurers/import-csv")
    assert resp.status_code == 422


def test_insurer_list(authenticated_client: TestClient):
    """GET /insurers — expect 200 and a list."""
    resp = authenticated_client.get("/insurers")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_csv_import_valid(authenticated_client: TestClient):
    """POST /insurers/import-csv with a minimal valid CSV — expect 200."""
    csv_content = (
        "Entity Name,Insurance Category,Insurance Type,Physical Address,Email,Telephone\n"
        "Test Insurer ZW,Short-term insurer,Motor,123 Harare St,info@test.co.zw,+263 77 000 0000\n"
    )
    resp = authenticated_client.post(
        "/insurers/import-csv",
        files={"file": ("insurers.csv", io.BytesIO(csv_content.encode()), "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "imported" in data or "updated" in data


def test_insurer_not_found(authenticated_client: TestClient):
    """GET /insurers/99999 — nonexistent insurer, expect 404."""
    resp = authenticated_client.get("/insurers/99999")
    assert resp.status_code == 404
