"""Tests for FastAPI endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_rag_result():
    """Mock RAG query result."""
    return {
        "answer": "Machine learning is a subset of AI that enables systems to learn from data.",
        "sources": [
            {
                "text": "Machine learning enables computers to learn without explicit programming.",
                "score": 0.95,
                "metadata": {"source": "ml_intro.txt"},
            },
            {
                "text": "AI encompasses various techniques including machine learning.",
                "score": 0.88,
                "metadata": {"source": "ai_overview.txt"},
            },
        ],
        "latency_ms": 234.5,
    }


def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()

    assert "name" in data
    assert data["name"] == "mini-lumina"
    assert "version" in data
    assert "endpoints" in data


def test_healthz_healthy(client):
    """Test health check when healthy."""
    with patch("app.main.get_mongo_client") as mock_get_client:
        mock_client = Mock()
        mock_client.health_check.return_value = True
        mock_get_client.return_value = mock_client

        response = client.get("/healthz")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert data["mongodb"] == "healthy"
        assert "timestamp" in data


def test_healthz_unhealthy(client):
    """Test health check when unhealthy."""
    with patch("app.main.get_mongo_client") as mock_get_client:
        mock_client = Mock()
        mock_client.health_check.return_value = False
        mock_get_client.return_value = mock_client

        response = client.get("/healthz")

        assert response.status_code == 503
        data = response.json()

        assert "status" in data["detail"]


def test_ask_endpoint_success(client, mock_rag_result):
    """Test /ask endpoint with successful query."""
    with patch("app.main.get_rag_engine") as mock_get_engine:
        mock_engine = Mock()
        mock_engine.query.return_value = mock_rag_result
        mock_get_engine.return_value = mock_engine

        request_data = {
            "question": "What is machine learning?",
            "top_k": 5,
            "temperature": 0.7,
        }

        response = client.post("/ask", json=request_data)

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "answer" in data
        assert "sources" in data
        assert "latency_ms" in data

        # Check answer
        assert data["answer"] == mock_rag_result["answer"]

        # Check sources
        assert len(data["sources"]) == 2
        assert data["sources"][0]["text"] == mock_rag_result["sources"][0]["text"]
        assert data["sources"][0]["score"] == mock_rag_result["sources"][0]["score"]

        # Verify RAG engine was called with correct params
        mock_engine.query.assert_called_once_with(
            question=request_data["question"],
            top_k=request_data["top_k"],
            filter_criteria=None,
            temperature=request_data["temperature"],
        )


def test_ask_endpoint_minimal_request(client, mock_rag_result):
    """Test /ask endpoint with minimal request (only question)."""
    with patch("app.main.get_rag_engine") as mock_get_engine:
        mock_engine = Mock()
        mock_engine.query.return_value = mock_rag_result
        mock_get_engine.return_value = mock_engine

        request_data = {"question": "What is AI?"}

        response = client.post("/ask", json=request_data)

        assert response.status_code == 200
        data = response.json()

        assert "answer" in data
        assert "sources" in data


def test_ask_endpoint_with_filters(client, mock_rag_result):
    """Test /ask endpoint with metadata filters."""
    with patch("app.main.get_rag_engine") as mock_get_engine:
        mock_engine = Mock()
        mock_engine.query.return_value = mock_rag_result
        mock_get_engine.return_value = mock_engine

        request_data = {
            "question": "What is AI?",
            "top_k": 3,
            "filter_criteria": {"metadata.source": "ai_intro.txt"},
        }

        response = client.post("/ask", json=request_data)

        assert response.status_code == 200

        # Verify filters were passed
        call_args = mock_engine.query.call_args
        assert call_args.kwargs["filter_criteria"] == request_data["filter_criteria"]


def test_ask_endpoint_empty_question(client):
    """Test /ask endpoint with empty question."""
    request_data = {"question": ""}

    response = client.post("/ask", json=request_data)

    # Should fail validation
    assert response.status_code == 422  # Unprocessable Entity


def test_ask_endpoint_missing_question(client):
    """Test /ask endpoint without question field."""
    request_data = {"top_k": 5}

    response = client.post("/ask", json=request_data)

    # Should fail validation
    assert response.status_code == 422


def test_ask_endpoint_invalid_top_k(client):
    """Test /ask endpoint with invalid top_k values."""
    # top_k too small
    response = client.post("/ask", json={"question": "Test?", "top_k": 0})
    assert response.status_code == 422

    # top_k too large
    response = client.post("/ask", json={"question": "Test?", "top_k": 100})
    assert response.status_code == 422


def test_ask_endpoint_invalid_temperature(client):
    """Test /ask endpoint with invalid temperature values."""
    # temperature too small
    response = client.post(
        "/ask", json={"question": "Test?", "temperature": -0.1}
    )
    assert response.status_code == 422

    # temperature too large
    response = client.post(
        "/ask", json={"question": "Test?", "temperature": 2.5}
    )
    assert response.status_code == 422


def test_ask_endpoint_error_handling(client):
    """Test /ask endpoint error handling."""
    with patch("app.main.get_rag_engine") as mock_get_engine:
        mock_engine = Mock()
        mock_engine.query.side_effect = Exception("Database connection failed")
        mock_get_engine.return_value = mock_engine

        request_data = {"question": "What is AI?"}

        response = client.post("/ask", json=request_data)

        assert response.status_code == 500
        assert "error" in response.text.lower() or "failed" in response.text.lower()


def test_ask_endpoint_long_question(client, mock_rag_result):
    """Test /ask endpoint with very long question."""
    with patch("app.main.get_rag_engine") as mock_get_engine:
        mock_engine = Mock()
        mock_engine.query.return_value = mock_rag_result
        mock_get_engine.return_value = mock_engine

        long_question = "What is AI? " * 500  # Very long question

        request_data = {"question": long_question}

        response = client.post("/ask", json=request_data)

        # Should still work
        assert response.status_code == 200


def test_ask_endpoint_special_characters(client, mock_rag_result):
    """Test /ask endpoint with special characters in question."""
    with patch("app.main.get_rag_engine") as mock_get_engine:
        mock_engine = Mock()
        mock_engine.query.return_value = mock_rag_result
        mock_get_engine.return_value = mock_engine

        request_data = {
            "question": "What is AI? 🤖 Can it understand émojis & spëcial chars?"
        }

        response = client.post("/ask", json=request_data)

        assert response.status_code == 200


def test_cors_headers(client):
    """Test CORS headers are present."""
    response = client.options("/ask")

    # CORS headers should be present
    assert "access-control-allow-origin" in response.headers
