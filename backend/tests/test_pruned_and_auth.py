"""Smoke tests for pruned routes and auth gates."""
from fastapi.testclient import TestClient


def test_root_removed(client: TestClient):
    assert client.get("/").status_code == 404


def test_root_health_removed(client: TestClient):
    assert client.get("/health").status_code == 404


def test_api_health_ok(client: TestClient):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json().get("status") == "healthy"


def test_auth_refresh_gone(client: TestClient):
    r = client.post("/api/v1/auth/refresh", headers={"Authorization": "Bearer x"})
    assert r.status_code in (404, 405)


def test_shares_gone(client: TestClient):
    r = client.get("/api/v1/users/me/shares", headers={"Authorization": "Bearer x"})
    assert r.status_code == 404


def test_health_catalog_gone(client: TestClient):
    assert client.get("/api/v1/health/catalog").status_code == 404


def test_users_me_requires_auth(client: TestClient, auth_headers: dict):
    r = client.get("/api/v1/users/me", headers=auth_headers)
    assert r.status_code in (401, 403)


def test_comparables_requires_auth(client: TestClient, auth_headers: dict):
    r = client.get(
        "/api/v1/comparables",
        params={"property_id": "00000000-0000-0000-0000-000000000000"},
        headers=auth_headers,
    )
    assert r.status_code in (401, 403)
