"""Embedding generation with OpenAI/Azure OpenAI, retry logic, and token counting."""

from typing import List, Optional
import time
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from openai import OpenAI, AzureOpenAI, RateLimitError, APIError

from app.config import settings
from app.utils import log_event, calculate_token_count


class EmbeddingClient:
    """Client for generating embeddings with retry and error handling."""

    def __init__(self):
        """Initialize OpenAI or Azure OpenAI client."""
        if settings.use_azure_openai:
            self.client = AzureOpenAI(
                api_key=settings.AZURE_OPENAI_API_KEY,
                api_version=settings.AZURE_OPENAI_API_VERSION,
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            )
            self.embedding_model = settings.AZURE_EMBEDDING_DEPLOYMENT
            log_event("embedding_client_initialized", {"provider": "azure_openai"})
        else:
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
            self.embedding_model = settings.EMBEDDING_MODEL
            log_event("embedding_client_initialized", {"provider": "openai"})

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIError)),
        stop=stop_after_attempt(settings.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _call_embedding_api(self, text: str) -> List[float]:
        """
        Call OpenAI embedding API with retry logic.

        Args:
            text: Input text to embed

        Returns:
            Embedding vector (list of floats)
        """
        response = self.client.embeddings.create(
            input=text,
            model=self.embedding_model,
        )
        return response.data[0].embedding

    def get_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for input text with error handling and logging.

        Args:
            text: Input text to embed

        Returns:
            Embedding vector (list of floats)

        Raises:
            Exception: If embedding generation fails after retries
        """
        if not text or not text.strip():
            log_event("empty_text_embedding_request", level="WARNING")
            raise ValueError("Cannot generate embedding for empty text")

        start_time = time.time()
        token_count = calculate_token_count(text, model=self.embedding_model)

        try:
            embedding = self._call_embedding_api(text)
            latency_ms = (time.time() - start_time) * 1000

            log_event(
                "embedding_generated",
                {
                    "text_length": len(text),
                    "token_count": token_count,
                    "embedding_dim": len(embedding),
                    "latency_ms": round(latency_ms, 2),
                    "model": self.embedding_model,
                },
            )

            return embedding

        except RateLimitError as e:
            log_event(
                "embedding_rate_limit_exceeded",
                {
                    "error": str(e),
                    "model": self.embedding_model,
                },
                level="ERROR",
            )
            raise

        except APIError as e:
            log_event(
                "embedding_api_error",
                {
                    "error": str(e),
                    "model": self.embedding_model,
                },
                level="ERROR",
            )
            raise

        except Exception as e:
            log_event(
                "embedding_generation_failed",
                {
                    "error": str(e),
                    "text_length": len(text),
                },
                level="ERROR",
            )
            raise

    def get_embeddings_batch(
        self, texts: List[str], batch_size: int = 100
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches.

        Args:
            texts: List of input texts
            batch_size: Number of texts to process per API call

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        start_time = time.time()
        embeddings = []

        try:
            # Process in batches
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]

                response = self.client.embeddings.create(
                    input=batch,
                    model=self.embedding_model,
                )

                batch_embeddings = [item.embedding for item in response.data]
                embeddings.extend(batch_embeddings)

            latency_ms = (time.time() - start_time) * 1000

            log_event(
                "batch_embeddings_generated",
                {
                    "num_texts": len(texts),
                    "batch_size": batch_size,
                    "latency_ms": round(latency_ms, 2),
                },
            )

            return embeddings

        except Exception as e:
            log_event(
                "batch_embedding_failed",
                {"error": str(e), "num_texts": len(texts)},
                level="ERROR",
            )
            raise


# Global embedding client instance
_embedding_client: Optional[EmbeddingClient] = None


def get_embedding_client() -> EmbeddingClient:
    """Get or create embedding client singleton."""
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = EmbeddingClient()
    return _embedding_client


def get_embedding(text: str) -> List[float]:
    """
    Convenience function to generate embedding.

    Args:
        text: Input text

    Returns:
        Embedding vector
    """
    client = get_embedding_client()
    return client.get_embedding(text)
