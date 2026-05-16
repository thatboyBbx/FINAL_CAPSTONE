"""
Tests for compliance-related endpoints.

The compliance checks are exposed via the documents router:
  POST /documents/{document_id}/compliance/recheck
  GET  /documents/{document_id}/compliance
  GET  /documents/compliance/statistics

There is no standalone /api/compliance/check endpoint; compliance is
document-centric and lives under the documents prefix.
"""
import pytest
from fastapi.testclient import TestClient


def test_compliance_statistics_empty(authenticated_client: TestClient):
    """GET /documents/compliance/statistics — expect 200 with zeroed-out stats."""
    resp = authenticated_client.get("/documents/compliance/statistics")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_documents_checked" in data


def test_compliance_check_invalid_id(authenticated_client: TestClient):
    """GET /documents/99999/compliance — document doesn't exist, expect 404."""
    resp = authenticated_client.get("/documents/99999/compliance")
    assert resp.status_code == 404


def test_compliance_recheck_missing_doc(authenticated_client: TestClient):
    """POST /documents/99999/compliance/recheck — document doesn't exist, expect 404."""
    resp = authenticated_client.post("/documents/99999/compliance/recheck")
    assert resp.status_code == 404
