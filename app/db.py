"""MongoDB Atlas connection and vector search operations."""

from typing import List, Dict, Any, Optional
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
import time

from app.config import settings
from app.utils import log_event


class MongoDBClient:
    """MongoDB client wrapper with vector search support."""

    def __init__(self):
        """Initialize MongoDB client."""
        self.client: Optional[MongoClient] = None
        self.db = None
        self.collection = None
        self._connect()

    def _connect(self):
        """Establish connection to MongoDB Atlas."""
        try:
            self.client = MongoClient(
                settings.MONGO_URI,
                serverSelectionTimeoutMS=5000,
                maxPoolSize=50,
            )
            # Test connection
            self.client.admin.command("ping")

            self.db = self.client[settings.MONGO_DB_NAME]
            self.collection = self.db[settings.MONGO_COLLECTION_NAME]

            log_event(
                "mongodb_connected",
                {
                    "database": settings.MONGO_DB_NAME,
                    "collection": settings.MONGO_COLLECTION_NAME,
                },
            )
        except ConnectionFailure as e:
            log_event(
                "mongodb_connection_failed",
                {"error": str(e)},
                level="ERROR",
            )
            raise

    def health_check(self) -> bool:
        """Check if MongoDB connection is healthy."""
        try:
            self.client.admin.command("ping")
            return True
        except Exception as e:
            log_event("mongodb_health_check_failed", {"error": str(e)}, level="ERROR")
            return False

    def upsert_document(
        self,
        doc_id: str,
        text: str,
        embedding: List[float],
        metadata: Dict[str, Any] = None,
    ) -> str:
        """
        Insert or update a document with its embedding.

        Args:
            doc_id: Unique document identifier
            text: Document text content
            embedding: Vector embedding (list of floats)
            metadata: Additional metadata

        Returns:
            Document ID
        """
        try:
            document = {
                "_id": doc_id,
                "text": text,
                "embedding": embedding,
                "metadata": metadata or {},
                "created_at": time.time(),
            }

            result = self.collection.replace_one(
                {"_id": doc_id}, document, upsert=True
            )

            log_event(
                "document_upserted",
                {
                    "doc_id": doc_id,
                    "text_length": len(text),
                    "embedding_dim": len(embedding),
                    "modified": result.modified_count > 0,
                },
            )

            return doc_id

        except Exception as e:
            log_event(
                "document_upsert_failed",
                {"doc_id": doc_id, "error": str(e)},
                level="ERROR",
            )
            raise

    def mongo_knn_search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_criteria: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform k-nearest neighbors search using MongoDB Atlas vector search.

        Args:
            query_embedding: Query vector embedding
            top_k: Number of results to return
            filter_criteria: Optional metadata filters

        Returns:
            List of documents with similarity scores
        """
        try:
            start_time = time.time()

            # MongoDB Atlas Vector Search aggregation pipeline
            # Using $search with knnBeta operator
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": settings.VECTOR_INDEX_NAME,
                        "queryVector": query_embedding,
                        "path": "embedding",
                        "numCandidates": 50,
                        "limit": top_k
                        }
                },
                {
                    "$project": {
                        "_id": 1,
                        "text": 1,
                        "metadata": 1,
                        "score": {"$meta": "searchScore"},
                    }
                },
                {"$limit": top_k},
            ]

            # Add filter criteria if provided
            if filter_criteria:
                # Insert match stage after search
                pipeline.insert(
                    1,
                    {"$match": filter_criteria},
                )

            results = list(self.collection.aggregate(pipeline))

            latency_ms = (time.time() - start_time) * 1000

            log_event(
                "knn_search_completed",
                {
                    "num_results": len(results),
                    "top_k": top_k,
                    "latency_ms": round(latency_ms, 2),
                    "has_filters": bool(filter_criteria),
                },
            )

            return results

        except OperationFailure as e:
            log_event(
                "knn_search_failed",
                {
                    "error": str(e),
                    "top_k": top_k,
                    "message": "Check if vector search index exists and is built",
                },
                level="ERROR",
            )
            raise
        except Exception as e:
            log_event(
                "knn_search_error",
                {"error": str(e), "top_k": top_k},
                level="ERROR",
            )
            raise

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a document by ID.

        Args:
            doc_id: Document identifier

        Returns:
            Document or None if not found
        """
        try:
            return self.collection.find_one({"_id": doc_id})
        except Exception as e:
            log_event(
                "get_document_failed",
                {"doc_id": doc_id, "error": str(e)},
                level="ERROR",
            )
            return None

    def count_documents(self, filter_criteria: Dict[str, Any] = None) -> int:
        """
        Count documents matching criteria.

        Args:
            filter_criteria: Optional filter

        Returns:
            Document count
        """
        try:
            return self.collection.count_documents(filter_criteria or {})
        except Exception as e:
            log_event(
                "count_documents_failed",
                {"error": str(e)},
                level="ERROR",
            )
            return 0

    def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            log_event("mongodb_connection_closed")


# Global MongoDB client instance
_mongo_client: Optional[MongoDBClient] = None


def get_mongo_client() -> MongoDBClient:
    """Get or create MongoDB client singleton."""
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = MongoDBClient()
    return _mongo_client
