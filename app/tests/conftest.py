"""Pytest configuration and shared fixtures."""

import pytest
from unittest.mock import Mock, MagicMock


@pytest.fixture
def mock_embedding():
    """Mock embedding vector."""
    return [0.1] * 1536  # OpenAI embedding dimension


@pytest.fixture
def mock_embedding_client(mock_embedding):
    """Mock embedding client."""
    mock_client = Mock()
    mock_client.get_embedding.return_value = mock_embedding
    mock_client.get_embeddings_batch.return_value = [mock_embedding] * 3
    return mock_client


@pytest.fixture
def mock_mongo_client():
    """Mock MongoDB client."""
    mock_client = Mock()
    mock_client.health_check.return_value = True
    mock_client.upsert_document.return_value = "test_doc_id"
    mock_client.mongo_knn_search.return_value = [
        {
            "_id": "doc_1",
            "text": "Sample document text 1",
            "score": 0.95,
            "metadata": {"source": "test.txt"},
        },
        {
            "_id": "doc_2",
            "text": "Sample document text 2",
            "score": 0.85,
            "metadata": {"source": "test.txt"},
        },
    ]
    mock_client.count_documents.return_value = 10
    return mock_client


@pytest.fixture
def mock_llm_client():
    """Mock LLM client."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.choices = [
        Mock(message=Mock(content="This is a mock answer to your question."))
    ]
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


@pytest.fixture
def sample_documents():
    """Sample documents for testing."""
    return [
        {
            "_id": "doc_1",
            "text": "Artificial intelligence is a branch of computer science.",
            "embedding": [0.1] * 1536,
            "metadata": {"source": "ai_intro.txt", "chunk_index": 0},
        },
        {
            "_id": "doc_2",
            "text": "Machine learning is a subset of artificial intelligence.",
            "embedding": [0.2] * 1536,
            "metadata": {"source": "ml_basics.txt", "chunk_index": 0},
        },
        {
            "_id": "doc_3",
            "text": "Deep learning uses neural networks with multiple layers.",
            "embedding": [0.3] * 1536,
            "metadata": {"source": "dl_overview.txt", "chunk_index": 0},
        },
    ]
