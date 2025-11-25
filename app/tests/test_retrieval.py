"""Tests for retrieval functionality."""

import pytest
from unittest.mock import Mock, patch
from app.rag_engine import RAGEngine


@pytest.fixture
def rag_engine_with_mocks(mock_mongo_client, mock_embedding_client, mock_llm_client):
    """Create RAG engine with mocked dependencies."""
    with patch("app.rag_engine.get_mongo_client", return_value=mock_mongo_client):
        with patch(
            "app.rag_engine.get_embedding_client", return_value=mock_embedding_client
        ):
            with patch("app.rag_engine.OpenAI", return_value=mock_llm_client):
                with patch("app.rag_engine.AzureOpenAI", return_value=mock_llm_client):
                    engine = RAGEngine()
                    engine.mongo_client = mock_mongo_client
                    engine.embedding_client = mock_embedding_client
                    engine.llm_client = mock_llm_client
                    return engine


def test_retrieve_basic(rag_engine_with_mocks, mock_mongo_client, mock_embedding_client):
    """Test basic retrieval."""
    query = "What is machine learning?"

    results = rag_engine_with_mocks.retrieve(query, top_k=5)

    # Verify embedding was generated for query
    mock_embedding_client.get_embedding.assert_called_once_with(query)

    # Verify vector search was called
    mock_mongo_client.mongo_knn_search.assert_called_once()

    # Check results
    assert len(results) == 2  # Mock returns 2 results
    assert all("text" in doc for doc in results)
    assert all("score" in doc for doc in results)


def test_retrieve_with_filters(rag_engine_with_mocks, mock_mongo_client):
    """Test retrieval with metadata filters."""
    query = "What is AI?"
    filters = {"metadata.source": "test.txt"}

    results = rag_engine_with_mocks.retrieve(query, top_k=3, filter_criteria=filters)

    # Verify filters were passed to search
    call_args = mock_mongo_client.mongo_knn_search.call_args
    assert call_args.kwargs["filter_criteria"] == filters


def test_retrieve_empty_query(rag_engine_with_mocks, mock_embedding_client):
    """Test retrieval with empty query."""
    mock_embedding_client.get_embedding.side_effect = ValueError(
        "Cannot generate embedding for empty text"
    )

    with pytest.raises(ValueError):
        rag_engine_with_mocks.retrieve("", top_k=5)


def test_build_prompt(rag_engine_with_mocks, sample_documents):
    """Test prompt building."""
    query = "What is AI?"
    retrieved_docs = [
        {
            "text": "AI is artificial intelligence.",
            "score": 0.95,
            "metadata": {"source": "ai.txt"},
        },
        {
            "text": "ML is machine learning.",
            "score": 0.85,
            "metadata": {"source": "ml.txt"},
        },
    ]

    prompt = rag_engine_with_mocks.build_prompt(query, retrieved_docs)

    # Verify prompt contains query
    assert query in prompt

    # Verify prompt contains retrieved documents
    assert "AI is artificial intelligence" in prompt
    assert "ML is machine learning" in prompt

    # Verify prompt has structure
    assert "Context Documents:" in prompt or "Document" in prompt
    assert "Question:" in prompt or query in prompt


def test_build_prompt_token_limit(rag_engine_with_mocks):
    """Test prompt building with token limit."""
    query = "What is AI?"

    # Create a very long document
    long_text = "This is a very long document. " * 1000

    retrieved_docs = [
        {"text": long_text, "score": 0.95, "metadata": {}},
    ]

    # Build prompt with small token limit
    prompt = rag_engine_with_mocks.build_prompt(
        query, retrieved_docs, max_context_tokens=100
    )

    # Prompt should be truncated
    assert len(prompt) < len(long_text)


def test_call_llm(rag_engine_with_mocks, mock_llm_client):
    """Test LLM calling."""
    prompt = "Answer this question: What is AI?"

    response = rag_engine_with_mocks.call_llm(prompt, temperature=0.7)

    # Verify LLM was called
    mock_llm_client.chat.completions.create.assert_called_once()

    # Check call arguments
    call_args = mock_llm_client.chat.completions.create.call_args
    assert call_args.kwargs["temperature"] == 0.7
    assert any("What is AI?" in str(msg) for msg in call_args.kwargs["messages"])

    # Check response
    assert isinstance(response, str)
    assert len(response) > 0


def test_call_llm_with_timeout(rag_engine_with_mocks, mock_llm_client):
    """Test LLM call with timeout."""
    # Mock timeout error
    mock_llm_client.chat.completions.create.side_effect = Exception("Request timed out")

    with pytest.raises(Exception):
        rag_engine_with_mocks.call_llm("Test prompt")


def test_query_full_pipeline(rag_engine_with_mocks):
    """Test full RAG query pipeline."""
    question = "What is machine learning?"

    result = rag_engine_with_mocks.query(question, top_k=5, temperature=0.7)

    # Check result structure
    assert "answer" in result
    assert "sources" in result
    assert "latency_ms" in result

    # Check answer
    assert isinstance(result["answer"], str)
    assert len(result["answer"]) > 0

    # Check sources
    assert isinstance(result["sources"], list)
    assert len(result["sources"]) > 0

    # Check source structure
    for source in result["sources"]:
        assert "text" in source
        assert "score" in source
        assert "metadata" in source


def test_query_no_results(rag_engine_with_mocks, mock_mongo_client):
    """Test query when no documents are retrieved."""
    # Mock no results
    mock_mongo_client.mongo_knn_search.return_value = []

    result = rag_engine_with_mocks.query("What is X?", top_k=5)

    # Should return a fallback message
    assert "answer" in result
    assert "couldn't find" in result["answer"].lower() or "no" in result["answer"].lower()
    assert result["sources"] == []


def test_query_with_error_handling(rag_engine_with_mocks, mock_embedding_client):
    """Test query error handling."""
    # Mock embedding error
    mock_embedding_client.get_embedding.side_effect = Exception("API Error")

    with pytest.raises(Exception):
        rag_engine_with_mocks.query("What is AI?")


def test_retrieve_custom_top_k(rag_engine_with_mocks, mock_mongo_client):
    """Test retrieval with custom top_k."""
    query = "Test query"

    # Test with different top_k values
    for k in [1, 3, 5, 10]:
        rag_engine_with_mocks.retrieve(query, top_k=k)

        # Verify top_k was passed correctly
        call_args = mock_mongo_client.mongo_knn_search.call_args
        assert call_args.kwargs["top_k"] == k
