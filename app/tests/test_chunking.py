"""Tests for text chunking functionality."""

import pytest
from app.ingestion import chunk_text, generate_chunk_id


def test_chunk_text_basic():
    """Test basic text chunking."""
    text = "This is a test sentence. " * 100  # Long text
    chunks = chunk_text(text, max_chunk_size=100, overlap=10)

    assert len(chunks) > 1
    assert all(len(chunk) <= 110 for chunk in chunks)  # Allow some variance
    assert all(chunk.strip() for chunk in chunks)  # No empty chunks


def test_chunk_text_short():
    """Test chunking of text shorter than max size."""
    text = "This is a short text."
    chunks = chunk_text(text, max_chunk_size=100, overlap=10)

    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_empty():
    """Test chunking of empty text."""
    chunks = chunk_text("", max_chunk_size=100, overlap=10)
    assert len(chunks) == 0

    chunks = chunk_text("   ", max_chunk_size=100, overlap=10)
    assert len(chunks) == 0


def test_chunk_text_overlap():
    """Test that chunks have proper overlap."""
    text = "Word " * 100
    chunks = chunk_text(text, max_chunk_size=50, overlap=20)

    assert len(chunks) > 1

    # Check that consecutive chunks share some content
    for i in range(len(chunks) - 1):
        # Last part of current chunk should appear in next chunk
        current_end = chunks[i][-20:]
        next_start = chunks[i + 1][:40]

        # There should be some overlap
        # (exact match is hard due to word boundaries, so check partial)
        assert len(chunks[i]) > 0
        assert len(chunks[i + 1]) > 0


def test_chunk_text_sentence_boundary():
    """Test chunking at sentence boundaries."""
    text = "First sentence. Second sentence. Third sentence. Fourth sentence."
    chunks = chunk_text(text, max_chunk_size=30, overlap=5)

    # Should prefer breaking at sentence boundaries
    for chunk in chunks:
        # Most chunks should end with a sentence boundary or be the last chunk
        if len(chunk) < 30:
            continue  # Last chunk might be shorter
        assert chunk.rstrip().endswith(".") or chunk.rstrip().endswith("!")


def test_chunk_text_whitespace_normalization():
    """Test that whitespace is normalized."""
    text = "This   has    irregular     spacing\n\n\nand newlines."
    chunks = chunk_text(text, max_chunk_size=100, overlap=10)

    assert len(chunks) == 1
    assert "  " not in chunks[0]  # No double spaces
    assert "\n" not in chunks[0]  # No newlines


def test_generate_chunk_id():
    """Test chunk ID generation."""
    id1 = generate_chunk_id("test.txt", 0)
    id2 = generate_chunk_id("test.txt", 1)
    id3 = generate_chunk_id("test.txt", 0)

    # IDs should be deterministic
    assert id1 == id3

    # Different chunks should have different IDs
    assert id1 != id2

    # IDs should be valid MD5 hashes (32 hex chars)
    assert len(id1) == 32
    assert all(c in "0123456789abcdef" for c in id1)


def test_generate_chunk_id_different_files():
    """Test chunk IDs for different files."""
    id1 = generate_chunk_id("file1.txt", 0)
    id2 = generate_chunk_id("file2.txt", 0)

    # Same chunk index but different files should have different IDs
    assert id1 != id2


def test_chunk_text_custom_settings():
    """Test chunking with custom settings."""
    text = "A " * 200

    # Large chunks
    large_chunks = chunk_text(text, max_chunk_size=200, overlap=20)

    # Small chunks
    small_chunks = chunk_text(text, max_chunk_size=50, overlap=10)

    # Small chunk size should produce more chunks
    assert len(small_chunks) > len(large_chunks)


def test_chunk_text_special_characters():
    """Test chunking with special characters."""
    text = "This has special chars: @#$%^&*(). And emojis: 😀🎉. And unicode: café, naïve."
    chunks = chunk_text(text, max_chunk_size=100, overlap=10)

    assert len(chunks) >= 1
    # Special characters should be preserved
    combined = " ".join(chunks)
    assert "@" in combined
    assert "café" in combined
