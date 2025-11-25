# Project Structure

```
mini-lumina/
├── .github/
│   └── workflows/
│       └── azure-deploy.yml      # CI/CD pipeline for Azure deployment
├── app/
│   ├── __init__.py
│   ├── config.py                 # Environment configuration
│   ├── db.py                     # MongoDB client and vector search
│   ├── embeddings.py             # OpenAI/Azure embedding client
│   ├── ingestion.py              # Document parsing and indexing
│   ├── main.py                   # FastAPI application
│   ├── rag_engine.py             # RAG orchestration
│   ├── utils.py                  # Logging and utilities
│   ├── eval.py                   # Evaluation script
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py           # Pytest fixtures
│       ├── test_api.py           # API endpoint tests
│       ├── test_chunking.py      # Text chunking tests
│       └── test_retrieval.py     # Retrieval logic tests
├── streamlit_app/
│   ├── app.py                    # Streamlit UI
│   └── Dockerfile                # Frontend container
├── .env.example                  # Example environment variables
├── .gitignore                    # Git ignore rules
├── docker-compose.yml            # Multi-service orchestration
├── Dockerfile                    # Backend container
├── eval_dataset.csv              # Sample evaluation data
├── Makefile                      # Development commands
├── PROJECT_STRUCTURE.md          # This file
├── QUICKSTART.md                 # 5-minute setup guide
├── pytest.ini                    # Pytest configuration
├── README.md                     # Full documentation
└── requirements.txt              # Python dependencies
```

## Key Components

### Backend (FastAPI)
- **main.py**: REST API with `/ask` and `/healthz` endpoints
- **db.py**: MongoDB Atlas vector search with `$search` + `knnBeta`
- **embeddings.py**: Embedding generation with retry logic
- **rag_engine.py**: Retrieval-augmented generation pipeline
- **ingestion.py**: Document processing (txt, pdf, markdown)
- **config.py**: Environment-based configuration
- **utils.py**: JSON logging utilities

### Frontend (Streamlit)
- **streamlit_app/app.py**: Interactive UI for querying the RAG system

### Testing
- **test_api.py**: FastAPI endpoint tests with mocked dependencies
- **test_chunking.py**: Text chunking logic tests
- **test_retrieval.py**: RAG retrieval pipeline tests
- **conftest.py**: Shared pytest fixtures

### Deployment
- **Dockerfile**: Multi-stage Python 3.11 image for backend
- **docker-compose.yml**: Local development with backend + frontend
- **.github/workflows/azure-deploy.yml**: CI/CD to Azure App Service via ACR

### Evaluation
- **eval.py**: Precision@K and latency metrics
- **eval_dataset.csv**: Sample evaluation questions

## Data Flow

1. **Ingestion**: Document → Parse → Chunk → Embed → MongoDB
2. **Query**: Question → Embed → Vector Search → Retrieve Docs
3. **Generation**: Docs + Question → Build Prompt → LLM → Answer
4. **Response**: Answer + Sources → User

## Configuration

All settings via environment variables (see `.env.example`):
- MongoDB URI and collection names
- OpenAI/Azure OpenAI credentials
- Chunking parameters (size, overlap)
- Model selection (embedding, LLM)
- Logging level

## Development Workflow

```bash
# Setup
make install

# Run tests
make test

# Start backend
make run-backend

# Start frontend (separate terminal)
make run-frontend

# Docker
make docker-up

# Ingest documents
make ingest FILE=path/to/doc.pdf

# Evaluate
make eval
```

## Deployment Workflow

1. **Push to main** → GitHub Actions triggered
2. **Run tests** → pytest with coverage
3. **Build image** → Docker build + tag
4. **Push to ACR** → Azure Container Registry
5. **Deploy to App Service** → Update container + env vars
6. **Health check** → Verify `/healthz` endpoint

## MongoDB Atlas Setup

Required index configuration:

```json
{
  "mappings": {
    "dynamic": true,
    "fields": {
      "embedding": {
        "type": "knnVector",
        "dimensions": 1536,
        "similarity": "cosine"
      },
      "text": {"type": "string"},
      "metadata": {"type": "document", "dynamic": true}
    }
  }
}
```

Index name: `vector_index`

## Extensions

To add new features:

1. **New file type**: Add parser to `ingestion.py`
2. **New endpoint**: Add route to `main.py`
3. **New metric**: Extend `eval.py`
4. **New model**: Update `config.py` and clients

## Production Considerations

- [ ] Add authentication (JWT, OAuth)
- [ ] Implement rate limiting
- [ ] Add Redis caching for queries
- [ ] Set up monitoring (Prometheus, Grafana)
- [ ] Configure Azure Key Vault for secrets
- [ ] Add request validation middleware
- [ ] Implement query logging for analytics
- [ ] Add vector index warm-up on startup
