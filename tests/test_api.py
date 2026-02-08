import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_home_page():
    """Test home page renders"""
    response = client.get("/")
    assert response.status_code == 200
    assert b"BeConversive" in response.content


def test_success_page():
    """Test success page renders"""
    response = client.get("/success")
    assert response.status_code == 200
    assert b"Confession Posted" in response.content


def test_submit_valid_confession():
    """Test submitting a valid confession"""
    response = client.post(
        "/api/submit",
        json={"text": "This is a test confession for the API."}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "confession_id" in data


def test_submit_empty_confession():
    """Test submitting empty confession"""
    response = client.post(
        "/api/submit",
        json={"text": ""}
    )
    assert response.status_code == 422  # Validation error


def test_submit_too_long_confession():
    """Test submitting overly long confession"""
    response = client.post(
        "/api/submit",
        json={"text": "x" * 600}
    )
    assert response.status_code == 400
    assert "maximum length" in response.json()["detail"].lower()


def test_rate_limiting():
    """Test rate limiting functionality"""
    # Submit multiple confessions
    for i in range(11):
        response = client.post(
            "/api/submit",
            json={"text": f"Test confession {i}"}
        )
        
        if i < 10:
            assert response.status_code == 200
        else:
            # 11th request should be rate limited
            assert response.status_code == 429
            assert "rate limit" in response.json()["detail"].lower()
