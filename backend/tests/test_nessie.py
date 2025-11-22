"""Tests for Nessie connection"""
import pytest
import os
from app.core.database import get_catalog
from app.core.config import settings


@pytest.mark.skipif(
    not os.getenv("ICEBERG_CATALOG_URI"),
    reason="ICEBERG_CATALOG_URI not set"
)
def test_nessie_connection():
    """Test connection to Nessie catalog"""
    try:
        catalog = get_catalog()
        assert catalog is not None
        # Try to list namespaces (basic operation)
        namespaces = catalog.list_namespaces()
        assert isinstance(namespaces, list)
        print(f"✅ Successfully connected to Nessie. Found {len(namespaces)} namespaces.")
    except Exception as e:
        pytest.fail(f"Failed to connect to Nessie: {e}")


def test_nessie_endpoint_format():
    """Test that Nessie endpoint is properly formatted"""
    # This test doesn't require actual connection
    uri = settings.ICEBERG_CATALOG_URI
    if uri:
        assert uri.startswith("http://") or uri.startswith("https://")
        assert "/api/v2" in uri or uri.endswith("/api/v2")

