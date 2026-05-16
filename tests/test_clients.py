"""
Tests for Client Management API endpoints.

All routes are under /api/clients prefix.
"""
import pytest
from fastapi.testclient import TestClient


def test_create_client(authenticated_client: TestClient):
    """POST /api/clients — create a new client."""
    resp = authenticated_client.post(
        "/api/clients",
        json={"name": "Test Client", "segment": "retail"},
    )
    assert resp.status_code in (200, 201), (
        f"Unexpected status {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert data.get("name") == "Test Client"


def test_get_clients(authenticated_client: TestClient):
    """GET /api/clients — expect 200 and a list."""
    resp = authenticated_client.get("/api/clients")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_client_expiry(authenticated_client: TestClient):
    """GET /api/clients/expiry — expect 200."""
    resp = authenticated_client.get("/api/clients/expiry")
    assert resp.status_code == 200


def test_client_renewals(authenticated_client: TestClient):
    """GET /api/clients/renewals — expect 200."""
    resp = authenticated_client.get("/api/clients/renewals")
    assert resp.status_code == 200


def test_get_client_not_found(authenticated_client: TestClient):
    """GET /api/clients/99999 — expect 404."""
    resp = authenticated_client.get("/api/clients/99999")
    assert resp.status_code == 404


def test_create_client_missing_name(authenticated_client: TestClient):
    """POST /api/clients with no name — expect 400."""
    resp = authenticated_client.post("/api/clients", json={"segment": "retail"})
    assert resp.status_code in (400, 422)
