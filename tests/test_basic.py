"""
Basic tests for the embedded insurance API.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_root_endpoint():
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "Embedded Insurance API"

def test_health_endpoint():
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_quotes_endpoint_authentication():
    """Test that quotes endpoint requires authentication."""
    response = client.post("/v1/quotes", json={})
    assert response.status_code == 403  # Forbidden due to missing auth

def test_bindings_endpoint_authentication():
    """Test that bindings endpoint requires authentication."""
    response = client.post("/v1/bindings", json={})
    assert response.status_code == 403  # Forbidden due to missing auth

def test_policies_endpoint_authentication():
    """Test that policies endpoint requires authentication."""
    response = client.get("/v1/policies/1")
    assert response.status_code == 403  # Forbidden due to missing auth

def test_portfolio_endpoint_authentication():
    """Test that portfolio endpoint requires authentication."""
    response = client.post("/v1/portfolio/simulate", json={})
    assert response.status_code == 403  # Forbidden due to missing auth

def test_quotes_endpoint_with_auth():
    """Test quotes endpoint with valid authentication."""
    headers = {"Authorization": "Bearer KLARITY_TEST_KEY"}
    data = {
        "product_code": "shipping",
        "partner_id": "ptnr_klarity",
        "declared_value": 650.0,
        "item_category": "electronics",
        "destination_state": "CA",
        "destination_risk": "medium",
        "service_level": "ground"
    }
    response = client.post("/v1/quotes", json=data, headers=headers)
    assert response.status_code == 200
    assert "quote_id" in response.json()
    assert response.json()["product_code"] == "shipping"

def test_bindings_endpoint_with_auth():
    """Test bindings endpoint with valid authentication."""
    headers = {"Authorization": "Bearer KLARITY_TEST_KEY"}
    data = {
        "quote_id": 1,
        "policyholder": {
            "name": "Test User",
            "email": "test@example.com",
            "state": "CA",
            "age": 30,
            "tenure_months": 12
        }
    }
    response = client.post("/v1/bindings", json=data, headers=headers)
    assert response.status_code == 200
    assert "policy_id" in response.json()
    assert response.json()["status"] == "active"
