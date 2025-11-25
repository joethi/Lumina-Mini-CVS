# Architecture Documentation

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interface                          │
│                                                                 │
│  ┌───────────────────────────────────────────────────────┐    │
│  │            Streamlit Frontend (Port 8501)             │    │
│  │  • Question input                                      │    │
│  │  • Answer display                                      │    │
│  │  • Source document viewer                              │    │
│  │  • Configuration controls                              │    │
│  └───────────────────────────────────────────────────────┘    │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP POST /ask
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Backend API Layer                         │
│                                                                 │
│  ┌───────────────────────────────────────────────────────┐    │
│  │           FastAPI Application (Port 8000)             │    │
│  │  ┌─────────────────────────────────────────────────┐ │    │
│  │  │  GET  /           - API info                    │ │    │
│  │  │  GET  /healthz    - Health check                │ │    │
│  │  │  POST /ask        - RAG query endpoint          │ │    │
│  │  │  GET  /docs       - OpenAPI documentation       │ │    │
│  │  └─────────────────────────────────────────────────┘ │    │
│  └───────────────────────────────────────────────────────┘    │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                       RAG Engine Core                           │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │                    RAG Pipeline Flow                      │ │
│  │                                                           │ │
│  │  1. Query Embedding                                       │ │
│  │     └─► get_embedding(query)                             │ │
│  │                                                           │ │
│  │  2. Vector Retrieval                                      │ │
│  │     └─► mongo_knn_search(query_embedding, top_k)         │ │
│  │                                                           │ │
│  │  3. Context Building                                      │ │
│  │     └─► build_prompt(query, retrieved_docs)              │ │
│  │                                                           │ │
│  │  4. Answer Generation                                     │ │
│  │     └─► call_llm(prompt, temperature)                    │ │
│  │                                                           │ │
│  │  5. Response Formatting                                   │ │
│  │     └─► format_response(answer, sources, metadata)       │ │
│  └──────────────────────────────────────────────────────────┘ │
└───────┬──────────────────────────────────┬──────────────────────┘
        │                                  │
        ▼                                  ▼
┌──────────────────────┐         ┌──────────────────────┐
│   OpenAI / Azure     │         │   MongoDB Atlas      │
│   OpenAI API         │         │   Vector Search      │
│                      │         │                      │
│  • Embeddings API    │         │  • Document store    │
│  • Chat Completions  │         │  • knnBeta search    │
│  • Token counting    │         │  • Metadata filters  │
└──────────────────────┘         └──────────────────────┘
```

## Component Architecture

### 1. Frontend Layer (Streamlit)

**File:** `streamlit_app/app.py`

**Responsibilities:**
- User interface for query input
- Display answers and source documents
- Configuration controls (top_k, temperature, filters)
- Backend health monitoring

**Key Functions:**
```python
check_backend_health() → bool
ask_question(question, top_k, temperature, filters) → Dict
main() → UI rendering
```

### 2. API Layer (FastAPI)

**File:** `app/main.py`

**Endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | API information |
| `/healthz` | GET | Health check (MongoDB status) |
| `/ask` | POST | RAG query execution |
| `/docs` | GET | Interactive API docs |

**Request/Response Models:**
```python
class AskRequest(BaseModel):
    question: str
    top_k: Optional[int] = 5
    temperature: Optional[float] = 0.7
    filter_criteria: Optional[Dict] = None

class AskResponse(BaseModel):
    answer: str
    sources: List[Source]
    latency_ms: float
```

### 3. RAG Engine

**File:** `app/rag_engine.py`

**Core Methods:**
```python
class RAGEngine:
    retrieve(query, top_k, filters) → List[Doc]
        ↓ Converts query to embedding
        ↓ Performs vector search
        ↓ Returns ranked documents

    build_prompt(query, docs, max_tokens) → str
        ↓ Formats documents as context
        ↓ Constructs structured prompt
        ↓ Applies token limits

    call_llm(prompt, temperature) → str
        ↓ Calls OpenAI/Azure API
        ↓ Handles retries & timeouts
        ↓ Returns generated answer

    query(question, top_k, filters, temp) → Dict
        ↓ Orchestrates full pipeline
        ↓ Returns answer + sources
```

### 4. Database Layer

**File:** `app/db.py`

**MongoDB Operations:**

```python
class MongoDBClient:
    upsert_document(doc_id, text, embedding, metadata)
        ↓ Stores document with vector
        ↓ Supports upsert semantics

    mongo_knn_search(query_embedding, top_k, filters)
        ↓ Uses MongoDB Atlas $search operator
        ↓ knnBeta vector search
        ↓ Returns documents with scores

    health_check() → bool
        ↓ Verifies connection
```

**Vector Search Pipeline:**
```python
pipeline = [
    {
        "$search": {
            "index": "vector_index",
            "knnBeta": {
                "vector": query_embedding,
                "path": "embedding",
                "k": top_k
            }
        }
    },
    {
        "$project": {
            "_id": 1,
            "text": 1,
            "metadata": 1,
            "score": {"$meta": "searchScore"}
        }
    }
]
```

### 5. Embedding Service

**File:** `app/embeddings.py`

**Responsibilities:**
- Generate embeddings via OpenAI/Azure API
- Retry logic with exponential backoff
- Token counting and optimization
- Batch processing support

```python
class EmbeddingClient:
    get_embedding(text: str) → List[float]
        ↓ Validates input
        ↓ Calls API with retry
        ↓ Returns 1536-dim vector
        ↓ Logs metrics

    get_embeddings_batch(texts: List[str]) → List[List[float]]
        ↓ Processes in batches
        ↓ Optimizes API calls
```

### 6. Ingestion Pipeline

**File:** `app/ingestion.py`

**Document Processing Flow:**

```
File Input
    ↓
parse_file(file_path)
    ↓ Detects file type (.txt, .pdf, .md)
    ↓ Extracts text content
    ↓
chunk_text(text, max_size, overlap)
    ↓ Splits into manageable chunks
    ↓ Respects sentence boundaries
    ↓ Applies overlap for context
    ↓
For each chunk:
    ↓
    generate_embedding(chunk)
        ↓
    upsert_to_mongodb(chunk_id, text, embedding, metadata)
```

**Chunking Strategy:**
```python
chunk_text(text, max_chunk_size=512, overlap=50)
    ↓ Normalize whitespace
    ↓ Prefer sentence boundaries
    ↓ Fall back to word boundaries
    ↓ Apply overlap between chunks
    ↓ Return list of chunks
```

### 7. Configuration Management

**File:** `app/config.py`

**Environment-Based Settings:**
```python
class Settings(BaseSettings):
    # MongoDB
    MONGO_URI: str
    MONGO_DB_NAME: str = "lumina"
    MONGO_COLLECTION_NAME: str = "documents"

    # OpenAI
    OPENAI_API_KEY: Optional[str]
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    LLM_MODEL: str = "gpt-4o-mini"

    # Azure OpenAI (alternative)
    AZURE_OPENAI_ENDPOINT: Optional[str]
    AZURE_OPENAI_API_KEY: Optional[str]

    # Application
    MAX_CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50
    TOP_K_RESULTS: int = 5
```

### 8. Logging & Observability

**File:** `app/utils.py`

**Structured JSON Logging:**
```json
{
  "timestamp": "2025-01-15T10:30:00.123Z",
  "level": "INFO",
  "event": "rag_query_completed",
  "context": {
    "question_length": 42,
    "num_sources": 5,
    "answer_length": 256,
    "latency_ms": 1234.5
  }
}
```

**Key Events Logged:**
- `mongodb_connected`
- `embedding_generated`
- `knn_search_completed`
- `llm_call_completed`
- `rag_query_completed`
- `document_upserted`
- `ingestion_completed`

## Data Flow Diagrams

### Ingestion Flow

```
┌─────────────┐
│  Document   │
│  (PDF/TXT)  │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  Parse File     │
│  Extract Text   │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  Chunk Text     │
│  (512 chars,    │
│   50 overlap)   │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  For Each Chunk │
│  ┌───────────┐  │
│  │ Embed     │  │
│  │ Generate  │  │
│  │ ID        │  │
│  └───────────┘  │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  MongoDB Atlas  │
│  {              │
│    _id: hash    │
│    text: str    │
│    embedding: [] │
│    metadata: {} │
│  }              │
└─────────────────┘
```

### Query Flow

```
┌─────────────┐
│  User Query │
│  "What is   │
│   ML?"      │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  Embed Query    │
│  → [0.1, 0.2..] │
└──────┬──────────┘
       │
       ▼
┌─────────────────────────┐
│  MongoDB Vector Search  │
│  $search → knnBeta      │
│  Returns top_k docs     │
│  with scores            │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────┐
│  Build Prompt   │
│  Context: docs  │
│  Question: query│
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  Call LLM       │
│  OpenAI GPT     │
│  Generate answer│
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  Format Response│
│  {              │
│    answer: str  │
│    sources: []  │
│    latency: ms  │
│  }              │
└──────┬──────────┘
       │
       ▼
┌─────────────┐
│  Return to  │
│  User       │
└─────────────┘
```

## Deployment Architecture

### Local Development

```
┌─────────────────────────────────────┐
│         Developer Machine           │
│                                     │
│  ┌─────────────┐  ┌──────────────┐ │
│  │  Backend    │  │  Frontend    │ │
│  │  :8000      │  │  :8501       │ │
│  └──────┬──────┘  └──────────────┘ │
│         │                           │
└─────────┼───────────────────────────┘
          │
          ▼
┌─────────────────────────────────────┐
│        External Services            │
│  ┌─────────────┐  ┌──────────────┐ │
│  │  MongoDB    │  │  OpenAI      │ │
│  │  Atlas      │  │  API         │ │
│  └─────────────┘  └──────────────┘ │
└─────────────────────────────────────┘
```

### Docker Deployment

```
┌─────────────────────────────────────┐
│       Docker Compose Network        │
│                                     │
│  ┌──────────────────────────────┐  │
│  │  Backend Container           │  │
│  │  mini-lumina-api:latest      │  │
│  │  Port: 8000                  │  │
│  └───────────┬──────────────────┘  │
│              │                      │
│  ┌───────────▼──────────────────┐  │
│  │  Frontend Container          │  │
│  │  mini-lumina-ui:latest       │  │
│  │  Port: 8501                  │  │
│  └──────────────────────────────┘  │
│                                     │
└─────────────────────────────────────┘
```

### Azure Production

```
┌──────────────────────────────────────────────────────┐
│                   GitHub Actions                      │
│  ┌────────────────────────────────────────────────┐  │
│  │  1. Run Tests (pytest)                         │  │
│  │  2. Build Docker Image                         │  │
│  │  3. Push to Azure Container Registry (ACR)     │  │
│  │  4. Deploy to Azure App Service                │  │
│  └────────────────────────────────────────────────┘  │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│            Azure Container Registry (ACR)            │
│  mini-lumina-api:latest                              │
│  mini-lumina-api:{git-sha}                           │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│              Azure App Service (Linux)               │
│  ┌────────────────────────────────────────────────┐  │
│  │  Web App: mini-lumina-api                      │  │
│  │  Plan: B1 (Basic)                              │  │
│  │  Runtime: Docker Container                     │  │
│  │  Port: 8000                                    │  │
│  │  URL: https://mini-lumina-api.azurewebsites.net│ │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
┌─────────────────┐     ┌──────────────────┐
│  MongoDB Atlas  │     │  OpenAI API      │
│  M10 Cluster    │     │  GPT-4 / Ada     │
│  Vector Index   │     │  Embeddings      │
└─────────────────┘     └──────────────────┘
```

## Security Architecture

### Authentication Flow (Future)

```
User → Frontend → API Gateway → JWT Validation → Backend
                      │
                      └─→ Azure AD / Auth0
```

### Secrets Management

```
Development:        .env file (gitignored)
Docker:             Environment variables
Azure Production:   Azure Key Vault
                    ↓
                    App Service Configuration
```

### Network Security

- HTTPS/TLS for all external communication
- CORS configured for frontend domain
- MongoDB IP whitelist
- Azure Private Endpoints (optional)
- API rate limiting (future)

## Scalability Considerations

### Horizontal Scaling

```
Load Balancer
    ├── Backend Instance 1
    ├── Backend Instance 2
    └── Backend Instance N
         ↓
    MongoDB Atlas (auto-scaling)
```

### Caching Strategy

```
Query → Redis Cache (check) → Hit: return cached
                ↓
              Miss:
                ↓
        RAG Pipeline → Cache result → Return
```

### Database Optimization

- Connection pooling (maxPoolSize=50)
- Index optimization for metadata filters
- Projection to limit returned fields
- Batch operations for ingestion

## Monitoring Architecture

### Metrics Collection

```
Application
    ↓ (JSON logs)
Azure Application Insights
    ↓
Azure Monitor Dashboard
    ↓
Alerts & Notifications
```

### Key Metrics

- Request latency (p50, p95, p99)
- Error rate
- MongoDB query performance
- OpenAI API latency
- Embedding generation time
- Cache hit rate (if implemented)

## Evaluation Framework

```
eval_dataset.csv
    ↓
Load Questions & Expected Docs
    ↓
For Each Question:
    ├── Retrieve Documents
    ├── Calculate Precision@K
    └── Measure Latency
    ↓
Aggregate Metrics
    ↓
eval_report.json
    ├── precision_at_1
    ├── precision_at_3
    ├── precision_at_5
    ├── avg_latency_ms
    └── detailed_results[]
```

## Technology Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | Streamlit | Interactive UI |
| Backend | FastAPI | REST API |
| Database | MongoDB Atlas | Document store + vector search |
| Embeddings | OpenAI/Azure | Text to vector conversion |
| LLM | GPT-4 / GPT-4o-mini | Answer generation |
| Container | Docker | Application packaging |
| Orchestration | Docker Compose | Multi-service management |
| CI/CD | GitHub Actions | Automated deployment |
| Cloud | Azure App Service | Hosting |
| Registry | Azure ACR | Container registry |
| Testing | Pytest | Unit/integration tests |
| Logging | JSON Logger | Structured logs |

## Design Patterns

### Singleton Pattern
- MongoDB client
- Embedding client
- RAG engine

### Factory Pattern
- Document parsers (txt, pdf, markdown)

### Strategy Pattern
- OpenAI vs Azure OpenAI provider selection

### Retry Pattern
- API calls with exponential backoff
- Tenacity library

### Repository Pattern
- Database operations abstraction

## Performance Characteristics

| Operation | Expected Latency |
|-----------|-----------------|
| Embedding generation | 50-200ms |
| Vector search | 100-300ms |
| LLM generation | 500-2000ms |
| End-to-end query | 1000-3000ms |
| Document ingestion (per chunk) | 100-300ms |

## Future Architecture Enhancements

1. **Microservices**: Split into separate services
2. **Event-Driven**: Use message queues for ingestion
3. **Real-time**: WebSocket for streaming responses
4. **Multi-tenancy**: Support multiple users/orgs
5. **Hybrid Search**: Combine vector + keyword search
6. **Conversation Memory**: Track dialogue history
7. **A/B Testing**: Compare model versions
