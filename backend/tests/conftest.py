"""Pytest fixtures — FastAPI TestClient harness."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict:
    """Placeholder bearer; endpoints should return 401 with invalid token."""
    return {"Authorization": "Bearer invalid-token"}
