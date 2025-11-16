"""
Integration tests for API server v3.0
Tests authentication, rate limiting, database, async orchestration
"""

import pytest
from fastapi.testclient import TestClient
from api.server import app, init_database, VALID_API_KEYS
import os
import sqlite3


# Test API keys
VALID_API_KEY = "demo-key-12345"
INVALID_API_KEY = "invalid-key"


@pytest.fixture(scope="module")
def client():
    """Create test client"""
    # Initialize test database
    init_database()
    return TestClient(app)


def test_root_endpoint(client):
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "3.0.0"
    assert "request_id" in data
    assert "features" in data


def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "3.0.0"
    assert data["status"] in ["healthy", "degraded"]


def test_list_agents(client):
    """Test list agents endpoint"""
    response = client.get("/agents")
    assert response.status_code == 200
    data = response.json()
    assert len(data["agents"]) == 6
    assert all("supports_llm" in agent for agent in data["agents"])


def test_authentication_required(client):
    """Test that authentication is required"""
    response = client.post(
        "/analyze",
        json={"incident_data": {"test": "data"}}
    )
    assert response.status_code == 401  # Unauthorized


def test_authentication_invalid_key(client):
    """Test with invalid API key"""
    response = client.post(
        "/analyze",
        json={"incident_data": {"test": "data"}},
        headers={"X-API-Key": INVALID_API_KEY}
    )
    assert response.status_code == 401  # Unauthorized


def test_create_analysis_with_auth(client):
    """Test creating analysis with valid authentication"""
    response = client.post(
        "/analyze",
        json={
            "incident_data": {
                "incident_time": "2025-01-15T10:00:00Z",
                "logs": [],
                "metrics": [],
                "changes": []
            }
        },
        headers={"X-API-Key": VALID_API_KEY}
    )
    assert response.status_code == 200
    data = response.json()
    assert "analysis_id" in data
    assert data["status"] == "queued"
    assert "request_id" in data


def test_get_analysis_status(client):
    """Test getting analysis status"""
    # Create analysis
    create_response = client.post(
        "/analyze",
        json={
            "incident_data": {
                "incident_time": "2025-01-15T10:00:00Z",
                "logs": [],
                "metrics": [],
                "changes": []
            }
        },
        headers={"X-API-Key": VALID_API_KEY}
    )
    analysis_id = create_response.json()["analysis_id"]

    # Get status
    response = client.get(
        f"/analyze/{analysis_id}",
        headers={"X-API-Key": VALID_API_KEY}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["analysis_id"] == analysis_id
    assert "status" in data
    assert "rate_limit_remaining" in data


def test_get_nonexistent_analysis(client):
    """Test getting nonexistent analysis"""
    response = client.get(
        "/analyze/nonexistent-id",
        headers={"X-API-Key": VALID_API_KEY}
    )
    assert response.status_code == 404


def test_execute_single_agent(client):
    """Test executing a single agent"""
    response = client.post(
        "/agents/log/execute",
        json={
            "context": {
                "logs": [
                    {"timestamp": "2025-01-15T10:00:00Z", "level": "ERROR", "message": "Test error", "service": "test"}
                ]
            },
            "parameters": {}
        },
        headers={"X-API-Key": VALID_API_KEY}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["agent_name"] == "LogAnalyzerAgent"
    assert "status" in data
    assert "findings" in data


def test_execute_invalid_agent(client):
    """Test executing invalid agent"""
    response = client.post(
        "/agents/invalid/execute",
        json={"context": {}},
        headers={"X-API-Key": VALID_API_KEY}
    )
    assert response.status_code == 404


def test_rate_limiting():
    """Test rate limiting (requires separate client to avoid interference)"""
    client = TestClient(app)

    # Make many requests quickly
    responses = []
    for i in range(105):  # Exceeds limit of 100
        response = client.post(
            "/analyze",
            json={
                "incident_data": {
                    "incident_time": "2025-01-15T10:00:00Z",
                    "logs": [],
                    "metrics": [],
                    "changes": []
                }
            },
            headers={"X-API-Key": VALID_API_KEY}
        )
        responses.append(response.status_code)

    # Some requests should be rate limited (429)
    assert 429 in responses


def test_request_id_header(client):
    """Test that X-Request-ID header is added"""
    response = client.get("/")
    assert "X-Request-ID" in response.headers


def test_stats_endpoint(client):
    """Test stats endpoint"""
    response = client.get(
        "/stats",
        headers={"X-API-Key": VALID_API_KEY}
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_analyses" in data
    assert "status_counts" in data
    assert "avg_execution_time_ms" in data
    assert "rate_limit_remaining" in data


def test_database_persistence():
    """Test that analyses are persisted to database"""
    client = TestClient(app)

    # Create analysis
    response = client.post(
        "/analyze",
        json={
            "incident_data": {
                "incident_time": "2025-01-15T10:00:00Z",
                "logs": [],
                "metrics": [],
                "changes": []
            }
        },
        headers={"X-API-Key": VALID_API_KEY}
    )
    analysis_id = response.json()["analysis_id"]

    # Check database directly
    conn = sqlite3.connect("adapt_agents.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, status FROM analyses WHERE id = ?", (analysis_id,))
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == analysis_id
    assert row[1] in ["queued", "running", "completed"]


def test_llm_flag(client):
    """Test LLM flag in request"""
    response = client.post(
        "/analyze",
        json={
            "incident_data": {
                "incident_time": "2025-01-15T10:00:00Z",
                "logs": [{"timestamp": "2025-01-15T10:00:00Z", "level": "ERROR", "message": "Test", "service": "test"}],
                "metrics": [],
                "changes": []
            },
            "use_llm": False,  # Set to False for testing without API keys
            "filter_pii": True
        },
        headers={"X-API-Key": VALID_API_KEY}
    )
    assert response.status_code == 200


def test_pii_filtering_flag(client):
    """Test PII filtering flag"""
    response = client.post(
        "/analyze",
        json={
            "incident_data": {
                "incident_time": "2025-01-15T10:00:00Z",
                "logs": [
                    {"timestamp": "2025-01-15T10:00:00Z", "level": "ERROR", "message": "User john@example.com failed", "service": "test"}
                ],
                "metrics": [],
                "changes": []
            },
            "filter_pii": True
        },
        headers={"X-API-Key": VALID_API_KEY}
    )
    assert response.status_code == 200
