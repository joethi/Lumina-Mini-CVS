"""Document ingestion: parsing, chunking, and indexing."""

import os
import hashlib
from pathlib import Path
from typing import List, Dict, Any
import re

from app.config import settings
from app.db import get_mongo_client
from app.embeddings import get_embedding_client
from app.utils import log_event


def parse_txt_file(file_path: str) -> str:
    """
    Parse plain text file.

    Args:
        file_path: Path to text file

    Returns:
        File content as string
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        log_event(
            "txt_parse_failed",
            {"file_path": file_path, "error": str(e)},
            level="ERROR",
        )
        raise


def parse_pdf_file(file_path: str) -> str:
    """
    Parse PDF file and extract text.

    Args:
        file_path: Path to PDF file

    Returns:
        Extracted text as string
    """
    try:
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        text = ""

        for page in reader.pages:
            text += page.extract_text() + "\n"

        return text
    except Exception as e:
        log_event(
            "pdf_parse_failed",
            {"file_path": file_path, "error": str(e)},
            level="ERROR",
        )
        raise


def parse_markdown_file(file_path: str) -> str:
    """
    Parse Markdown file.

    Args:
        file_path: Path to Markdown file

    Returns:
        File content as string (raw markdown)
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        log_event(
            "markdown_parse_failed",
            {"file_path": file_path, "error": str(e)},
            level="ERROR",
        )
        raise


def parse_file(file_path: str) -> str:
    """
    Parse file based on extension.

    Args:
        file_path: Path to file

    Returns:
        Extracted text content

    Raises:
        ValueError: If file type is not supported
    """
    ext = Path(file_path).suffix.lower()

    parsers = {
        ".txt": parse_txt_file,
        ".md": parse_markdown_file,
        ".markdown": parse_markdown_file,
        ".pdf": parse_pdf_file,
    }

    parser = parsers.get(ext)
    if not parser:
        raise ValueError(f"Unsupported file type: {ext}")

    log_event("parsing_file", {"file_path": file_path, "extension": ext})
    return parser(file_path)


def chunk_text(
    text: str,
    max_chunk_size: int = None,
    overlap: int = None,
) -> List[str]:
    """
    Split text into overlapping chunks.

    Args:
        text: Input text to chunk
        max_chunk_size: Maximum characters per chunk
        overlap: Number of overlapping characters between chunks

    Returns:
        List of text chunks
    """
    max_chunk_size = max_chunk_size or settings.MAX_CHUNK_SIZE
    overlap = overlap or settings.CHUNK_OVERLAP

    if not text or not text.strip():
        return []

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # If text is shorter than max_chunk_size, return as single chunk
    if len(text) <= max_chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        # Calculate end position
        end = start + max_chunk_size

        # If this is not the last chunk, try to break at sentence or word boundary
        if end < len(text):
            # Look for sentence boundary (. ! ? followed by space)
            sentence_end = max(
                text.rfind(". ", start, end),
                text.rfind("! ", start, end),
                text.rfind("? ", start, end),
            )

            if sentence_end > start:
                end = sentence_end + 1
            else:
                # Fall back to word boundary
                word_end = text.rfind(" ", start, end)
                if word_end > start:
                    end = word_end

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move start position with overlap
        start = end - overlap if end < len(text) else end

    log_event(
        "text_chunked",
        {
            "text_length": len(text),
            "num_chunks": len(chunks),
            "max_chunk_size": max_chunk_size,
            "overlap": overlap,
        },
    )

    return chunks


def generate_chunk_id(file_path: str, chunk_index: int) -> str:
    """
    Generate unique ID for a document chunk.

    Args:
        file_path: Source file path
        chunk_index: Index of chunk within file

    Returns:
        Unique chunk ID
    """
    # Create deterministic ID based on file path and chunk index
    content = f"{file_path}:{chunk_index}"
    return hashlib.md5(content.encode()).hexdigest()


def ingest_file(
    file_path: str,
    metadata: Dict[str, Any] = None,
) -> List[str]:
    """
    Ingest a file: parse, chunk, embed, and store in MongoDB.

    Args:
        file_path: Path to file to ingest
        metadata: Additional metadata to attach to chunks

    Returns:
        List of chunk IDs that were ingested

    Raises:
        Exception: If ingestion fails
    """
    try:
        # Validate file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        log_event("ingestion_started", {"file_path": file_path})

        # Parse file
        text = parse_file(file_path)

        if not text.strip():
            log_event(
                "empty_file_skipped",
                {"file_path": file_path},
                level="WARNING",
            )
            return []

        # Chunk text
        chunks = chunk_text(text)

        if not chunks:
            log_event(
                "no_chunks_generated",
                {"file_path": file_path},
                level="WARNING",
            )
            return []

        # Get clients
        mongo_client = get_mongo_client()
        embedding_client = get_embedding_client()

        # Process chunks
        chunk_ids = []

        for i, chunk in enumerate(chunks):
            chunk_id = generate_chunk_id(file_path, i)

            # Generate embedding
            embedding = embedding_client.get_embedding(chunk)

            # Prepare metadata
            chunk_metadata = {
                "source_file": file_path,
                "chunk_index": i,
                "total_chunks": len(chunks),
                **(metadata or {}),
            }

            # Store in MongoDB
            mongo_client.upsert_document(
                doc_id=chunk_id,
                text=chunk,
                embedding=embedding,
                metadata=chunk_metadata,
            )

            chunk_ids.append(chunk_id)

        log_event(
            "ingestion_completed",
            {
                "file_path": file_path,
                "num_chunks": len(chunk_ids),
                "chunk_ids": chunk_ids,
            },
        )

        return chunk_ids

    except Exception as e:
        log_event(
            "ingestion_failed",
            {"file_path": file_path, "error": str(e)},
            level="ERROR",
        )
        raise


def ingest_directory(
    directory_path: str,
    metadata: Dict[str, Any] = None,
    recursive: bool = True,
) -> Dict[str, List[str]]:
    """
    Ingest all supported files in a directory.

    Args:
        directory_path: Path to directory
        metadata: Metadata to attach to all chunks
        recursive: Whether to recursively process subdirectories

    Returns:
        Dictionary mapping file paths to chunk IDs
    """
    supported_extensions = {".txt", ".md", ".markdown", ".pdf"}
    results = {}

    try:
        directory = Path(directory_path)

        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory_path}")

        # Find all supported files
        pattern = "**/*" if recursive else "*"
        files = [
            f
            for f in directory.glob(pattern)
            if f.is_file() and f.suffix.lower() in supported_extensions
        ]

        log_event(
            "directory_ingestion_started",
            {
                "directory": directory_path,
                "num_files": len(files),
                "recursive": recursive,
            },
        )

        # Ingest each file
        for file_path in files:
            try:
                chunk_ids = ingest_file(str(file_path), metadata=metadata)
                results[str(file_path)] = chunk_ids
            except Exception as e:
                log_event(
                    "file_ingestion_failed_in_batch",
                    {"file_path": str(file_path), "error": str(e)},
                    level="ERROR",
                )
                # Continue with other files
                results[str(file_path)] = []

        log_event(
            "directory_ingestion_completed",
            {
                "directory": directory_path,
                "files_processed": len(results),
                "total_chunks": sum(len(chunks) for chunks in results.values()),
            },
        )

        return results

    except Exception as e:
        log_event(
            "directory_ingestion_failed",
            {"directory": directory_path, "error": str(e)},
            level="ERROR",
        )
        raise


# CLI entrypoint
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m app.ingestion <file_or_directory_path>")
        sys.exit(1)

    path = sys.argv[1]

    if os.path.isfile(path):
        chunk_ids = ingest_file(path)
        print(f"Ingested {len(chunk_ids)} chunks from {path}")
    elif os.path.isdir(path):
        results = ingest_directory(path)
        total_chunks = sum(len(chunks) for chunks in results.values())
        print(f"Ingested {total_chunks} chunks from {len(results)} files in {path}")
    else:
        print(f"Error: {path} is not a valid file or directory")
        sys.exit(1)
