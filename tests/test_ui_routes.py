"""
Smoke tests for all UI route paths.

Routes protected by auth redirect to "/" (303) when no cookie is present.
Unprotected routes (like login page) return 200 directly.
All responses should be 200, 302, or 303 — never 404 or 500.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize("path", [
    "/",
    "/home",
    "/documents",
    "/analysis",
    "/intelligence",
    "/reports",
    "/clients",
    "/system",
    "/documents/vault",
    "/documents/upload",
    "/documents/compare",
    "/analysis/ml",
    "/analysis/deviation",
    "/analysis/ner",
    "/analysis/risk",
    "/intelligence/insurers",
    "/intelligence/settlement-power",
    "/intelligence/advisory",
    "/reports/compliance",
    "/reports/generate",
    "/reports/news",
    "/clients/list",
    "/clients/expiry",
    "/clients/renewals",
    "/system/settings",
    "/system/audit",
])
def test_ui_route_exists(client: TestClient, path: str):
    """All UI routes must return 200 or a redirect (302/303), never 404 or 500."""
    resp = client.get(path, follow_redirects=False)
    assert resp.status_code in (200, 302, 303), (
        f"{path} returned {resp.status_code}"
    )
