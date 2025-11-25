"""RAG engine: retrieval, prompt building, and LLM calling."""

from typing import List, Dict, Any, Optional
import time
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from openai import OpenAI, AzureOpenAI, RateLimitError, APIError, Timeout

from app.config import settings
from app.db import get_mongo_client
from app.embeddings import get_embedding_client
from app.utils import log_event, calculate_token_count, truncate_text


class RAGEngine:
    """Retrieval-Augmented Generation engine."""

    def __init__(self):
        """Initialize RAG engine with LLM client."""
        if settings.use_azure_openai:
            self.llm_client = AzureOpenAI(
                api_key=settings.AZURE_OPENAI_API_KEY,
                api_version=settings.AZURE_OPENAI_API_VERSION,
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            )
            self.llm_model = settings.AZURE_LLM_DEPLOYMENT
            log_event("rag_engine_initialized", {"provider": "azure_openai"})
        else:
            self.llm_client = OpenAI(api_key=settings.OPENAI_API_KEY)
            self.llm_model = settings.LLM_MODEL
            log_event("rag_engine_initialized", {"provider": "openai"})

        self.mongo_client = get_mongo_client()
        self.embedding_client = get_embedding_client()

    def retrieve(
        self,
        query: str,
        top_k: int = None,
        filter_criteria: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant documents for a query.

        Args:
            query: User query
            top_k: Number of results to retrieve
            filter_criteria: Optional metadata filters

        Returns:
            List of retrieved documents with scores
        """
        top_k = top_k or settings.TOP_K_RESULTS

        try:
            # Generate query embedding
            query_embedding = self.embedding_client.get_embedding(query)

            # Perform vector search
            results = self.mongo_client.mongo_knn_search(
                query_embedding=query_embedding,
                top_k=top_k,
                filter_criteria=filter_criteria,
            )

            log_event(
                "retrieval_completed",
                {
                    "query_length": len(query),
                    "num_results": len(results),
                    "top_k": top_k,
                },
            )

            return results

        except Exception as e:
            log_event(
                "retrieval_failed",
                {"query": query[:100], "error": str(e)},
                level="ERROR",
            )
            raise

    def build_prompt(
        self,
        query: str,
        retrieved_docs: List[Dict[str, Any]],
        max_context_tokens: int = 3000,
    ) -> str:
        """
        Build prompt with retrieved context.

        Args:
            query: User query
            retrieved_docs: Retrieved documents
            max_context_tokens: Maximum tokens for context

        Returns:
            Formatted prompt
        """
        # Build context from retrieved documents
        context_parts = []
        current_tokens = 0

        for i, doc in enumerate(retrieved_docs, 1):
            doc_text = doc.get("text", "")
            doc_tokens = calculate_token_count(doc_text)

            # Check if adding this document would exceed limit
            if current_tokens + doc_tokens > max_context_tokens:
                # Truncate this document to fit
                remaining_tokens = max_context_tokens - current_tokens
                if remaining_tokens > 100:  # Only add if meaningful space left
                    doc_text = truncate_text(doc_text, remaining_tokens)
                else:
                    break

            context_parts.append(f"[Document {i}]\n{doc_text}")
            current_tokens += doc_tokens

        context = "\n\n".join(context_parts)

        # Build final prompt
        prompt = f"""You are a helpful AI assistant. Answer the user's question based on the provided context documents. If the context doesn't contain enough information to answer the question, say so honestly.

Context Documents:
{context}

User Question: {query}

Answer:"""

        log_event(
            "prompt_built",
            {
                "num_docs": len(context_parts),
                "context_tokens": current_tokens,
                "prompt_length": len(prompt),
            },
        )

        return prompt

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIError, Timeout)),
        stop=stop_after_attempt(settings.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _call_llm_api(self, prompt: str, temperature: float = 0.7) -> str:
        """
        Call LLM API with retry logic.

        Args:
            prompt: Input prompt
            temperature: Sampling temperature

        Returns:
            Generated text
        """
        response = self.llm_client.chat.completions.create(
            model=self.llm_model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful AI assistant that answers questions based on provided context.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=1000,
            timeout=settings.API_TIMEOUT,
        )

        return response.choices[0].message.content

    def call_llm(
        self,
        prompt: str,
        temperature: float = 0.7,
    ) -> str:
        """
        Call LLM with error handling and logging.

        Args:
            prompt: Input prompt
            temperature: Sampling temperature

        Returns:
            Generated text

        Raises:
            Exception: If LLM call fails after retries
        """
        start_time = time.time()
        prompt_tokens = calculate_token_count(prompt, model=self.llm_model)

        try:
            response = self._call_llm_api(prompt, temperature)
            latency_ms = (time.time() - start_time) * 1000
            response_tokens = calculate_token_count(response, model=self.llm_model)

            log_event(
                "llm_call_completed",
                {
                    "prompt_tokens": prompt_tokens,
                    "response_tokens": response_tokens,
                    "total_tokens": prompt_tokens + response_tokens,
                    "latency_ms": round(latency_ms, 2),
                    "model": self.llm_model,
                },
            )

            return response

        except RateLimitError as e:
            log_event(
                "llm_rate_limit_exceeded",
                {"error": str(e), "model": self.llm_model},
                level="ERROR",
            )
            raise

        except Timeout as e:
            log_event(
                "llm_timeout",
                {"error": str(e), "timeout": settings.API_TIMEOUT},
                level="ERROR",
            )
            raise

        except APIError as e:
            log_event(
                "llm_api_error",
                {"error": str(e), "model": self.llm_model},
                level="ERROR",
            )
            raise

        except Exception as e:
            log_event(
                "llm_call_failed",
                {"error": str(e)},
                level="ERROR",
            )
            raise

    def query(
        self,
        question: str,
        top_k: int = None,
        filter_criteria: Dict[str, Any] = None,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Execute full RAG pipeline: retrieve, build prompt, and generate answer.

        Args:
            question: User question
            top_k: Number of documents to retrieve
            filter_criteria: Optional metadata filters
            temperature: LLM sampling temperature

        Returns:
            Dictionary with answer, sources, and metadata
        """
        start_time = time.time()

        try:
            log_event("rag_query_started", {"question": question[:100]})

            # Retrieve relevant documents
            retrieved_docs = self.retrieve(
                query=question,
                top_k=top_k,
                filter_criteria=filter_criteria,
            )

            if not retrieved_docs:
                log_event(
                    "no_documents_retrieved",
                    {"question": question[:100]},
                    level="WARNING",
                )
                return {
                    "answer": "I couldn't find any relevant information to answer your question.",
                    "sources": [],
                    "latency_ms": round((time.time() - start_time) * 1000, 2),
                }

            # Build prompt
            prompt = self.build_prompt(question, retrieved_docs)

            # Generate answer
            answer = self.call_llm(prompt, temperature=temperature)

            latency_ms = (time.time() - start_time) * 1000

            # Format sources
            sources = [
                {
                    "text": doc.get("text", ""),
                    "score": doc.get("score", 0.0),
                    "metadata": doc.get("metadata", {}),
                }
                for doc in retrieved_docs
            ]

            result = {
                "answer": answer,
                "sources": sources,
                "latency_ms": round(latency_ms, 2),
            }

            log_event(
                "rag_query_completed",
                {
                    "question_length": len(question),
                    "num_sources": len(sources),
                    "answer_length": len(answer),
                    "latency_ms": round(latency_ms, 2),
                },
            )

            return result

        except Exception as e:
            log_event(
                "rag_query_failed",
                {"question": question[:100], "error": str(e)},
                level="ERROR",
            )
            raise


# Global RAG engine instance
_rag_engine: Optional[RAGEngine] = None


def get_rag_engine() -> RAGEngine:
    """Get or create RAG engine singleton."""
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine()
    return _rag_engine
