"""FastAPI application with /ask and /healthz endpoints."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import time

from app.config import settings
from app.db import get_mongo_client
from app.rag_engine import get_rag_engine
from app.utils import log_event

# Initialize FastAPI app
app = FastAPI(
    title="mini-lumina",
    description="A minimal RAG system with MongoDB Atlas vector search",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class AskRequest(BaseModel):
    """Request model for /ask endpoint."""

    question: str = Field(..., min_length=1, description="User question")
    top_k: Optional[int] = Field(
        None, ge=1, le=20, description="Number of documents to retrieve"
    )
    temperature: Optional[float] = Field(
        0.7, ge=0.0, le=2.0, description="LLM temperature"
    )
    filter_criteria: Optional[Dict[str, Any]] = Field(
        None, description="Optional metadata filters"
    )


class Source(BaseModel):
    """Source document model."""

    text: str
    score: float
    metadata: Dict[str, Any]


class AskResponse(BaseModel):
    """Response model for /ask endpoint."""

    answer: str
    sources: List[Source]
    latency_ms: float


class HealthResponse(BaseModel):
    """Response model for /healthz endpoint."""

    status: str
    mongodb: str
    timestamp: float


@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup."""
    log_event("application_startup", {"version": "0.1.0"})

    # Test MongoDB connection
    try:
        mongo_client = get_mongo_client()
        if mongo_client.health_check():
            log_event("startup_mongodb_ok")
        else:
            log_event("startup_mongodb_failed", level="ERROR")
    except Exception as e:
        log_event("startup_mongodb_error", {"error": str(e)}, level="ERROR")

    # Initialize RAG engine
    try:
        get_rag_engine()
        log_event("startup_rag_engine_ok")
    except Exception as e:
        log_event("startup_rag_engine_error", {"error": str(e)}, level="ERROR")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    log_event("application_shutdown")

    try:
        mongo_client = get_mongo_client()
        mongo_client.close()
    except Exception as e:
        log_event("shutdown_error", {"error": str(e)}, level="ERROR")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "mini-lumina",
        "version": "0.1.0",
        "description": "A minimal RAG system with MongoDB Atlas vector search",
        "endpoints": {
            "health": "/healthz",
            "ask": "/ask",
            "docs": "/docs",
        },
    }


@app.get("/healthz", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns:
        Health status of the application and dependencies
    """
    start_time = time.time()

    # Check MongoDB
    mongodb_status = "healthy"
    try:
        mongo_client = get_mongo_client()
        if not mongo_client.health_check():
            mongodb_status = "unhealthy"
    except Exception as e:
        mongodb_status = f"error: {str(e)}"
        log_event("healthz_mongodb_error", {"error": str(e)}, level="ERROR")

    overall_status = "healthy" if mongodb_status == "healthy" else "unhealthy"

    latency_ms = (time.time() - start_time) * 1000

    log_event(
        "health_check",
        {
            "status": overall_status,
            "mongodb": mongodb_status,
            "latency_ms": round(latency_ms, 2),
        },
    )

    response = HealthResponse(
        status=overall_status,
        mongodb=mongodb_status,
        timestamp=time.time(),
    )

    if overall_status == "unhealthy":
        raise HTTPException(status_code=503, detail=response.dict())

    return response


@app.post("/ask", response_model=AskResponse)
async def ask_question(request: AskRequest):
    """
    Ask a question and get an answer using RAG.

    Args:
        request: Question and retrieval parameters

    Returns:
        Answer with source documents and metadata
    """
    try:
        log_event(
            "ask_request_received",
            {
                "question_length": len(request.question),
                "top_k": request.top_k,
                "temperature": request.temperature,
            },
        )

        # Get RAG engine
        rag_engine = get_rag_engine()

        # Execute RAG query
        result = rag_engine.query(
            question=request.question,
            top_k=request.top_k,
            filter_criteria=request.filter_criteria,
            temperature=request.temperature,
        )

        # Format response
        sources = [
            Source(
                text=src["text"],
                score=src["score"],
                metadata=src["metadata"],
            )
            for src in result["sources"]
        ]

        response = AskResponse(
            answer=result["answer"],
            sources=sources,
            latency_ms=result["latency_ms"],
        )

        log_event(
            "ask_request_completed",
            {
                "question_length": len(request.question),
                "answer_length": len(response.answer),
                "num_sources": len(sources),
                "latency_ms": response.latency_ms,
            },
        )

        return response

    except Exception as e:
        log_event(
            "ask_request_failed",
            {
                "question": request.question[:100],
                "error": str(e),
            },
            level="ERROR",
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process question: {str(e)}",
        )


# For development
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.LOG_LEVEL.lower(),
    )
