# mini-lumina

A minimal, production-ready Retrieval-Augmented Generation (RAG) system using MongoDB Atlas vector search and Azure App Service.

## Architecture

- **Backend**: FastAPI + MongoDB Atlas Vector Search
- **Frontend**: Streamlit UI
- **Embeddings**: OpenAI/Azure OpenAI
- **LLM**: OpenAI ChatCompletion/Azure OpenAI
- **Deployment**: Docker + Azure Container Registry + Azure App Service
- **CI/CD**: GitHub Actions

## Prerequisites

1. **MongoDB Atlas Account**
   - Create a cluster (M10+ recommended for vector search)
   - Create a database `lumina` and collection `documents`
   - Whitelist your IP and get connection URI

2. **OpenAI or Azure OpenAI Account**
   - Get API keys for embeddings and chat completion

3. **Azure Account** (for deployment)
   - Azure Container Registry
   - Azure App Service (Linux, Docker container)

## Environment Variables

Create a `.env` file in the project root:

```bash
# MongoDB
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
MONGO_DB_NAME=lumina
MONGO_COLLECTION_NAME=documents

# OpenAI (use either OpenAI or Azure OpenAI)
OPENAI_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-small
LLM_MODEL=gpt-4o-mini

# Azure OpenAI (alternative to OpenAI)
# AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
# AZURE_OPENAI_API_KEY=...
# AZURE_OPENAI_API_VERSION=2024-02-15-preview
# AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-small
# AZURE_LLM_DEPLOYMENT=gpt-4

# App Config
LOG_LEVEL=INFO
MAX_CHUNK_SIZE=512
CHUNK_OVERLAP=50
TOP_K_RESULTS=5
```

## MongoDB Atlas Vector Search Index Setup

1. In MongoDB Atlas UI, navigate to your cluster → Search → Create Search Index
2. Use JSON Editor and paste:

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
      "text": {
        "type": "string"
      },
      "metadata": {
        "type": "document",
        "dynamic": true
      }
    }
  }
}
```

3. Name the index: `vector_index`
4. Select database: `lumina`, collection: `documents`
5. Wait for index to build (usually 1-2 minutes)

## Local Development

### Install Dependencies

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Run Backend API

```bash
cd mini-lumina
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API available at: http://localhost:8000
Docs: http://localhost:8000/docs

### Run Streamlit Frontend

```bash
cd mini-lumina
streamlit run streamlit_app/app.py
```

UI available at: http://localhost:8501

### Ingest Documents

```bash
python -m app.ingestion path/to/your/document.pdf
python -m app.ingestion path/to/folder/
```

### Run Tests

```bash
pytest app/tests/ -v --cov=app
```

## Docker Deployment

### Build and Run Locally

```bash
# Build backend
docker build -t mini-lumina-api .

# Run backend
docker run -p 8000:8000 --env-file .env mini-lumina-api

# Build frontend (optional)
docker build -f streamlit_app/Dockerfile -t mini-lumina-ui streamlit_app/

# Run frontend
docker run -p 8501:8501 -e BACKEND_URL=http://localhost:8000 mini-lumina-ui
```

### Docker Compose (Optional)

```bash
docker-compose up --build
```

## Azure Deployment

This guide works with **Azure for Students** subscriptions.

### Prerequisites

- Azure for Students account (with $100 credit)
- MongoDB Atlas account (use free M0 tier)
- OpenAI API key (or apply for Azure OpenAI)
- GitHub account

### Understanding the Architecture

**How OpenAI API Works in Azure:**
```
User Request → Azure App Service (your app) → OpenAI API (external service)
                      ↑
              Uses OPENAI_API_KEY from environment variables
```

Your app runs on Azure, but calls OpenAI's external API. The API key is:
- Stored as a GitHub Secret (secure)
- Injected into Azure App Service as an environment variable (by GitHub Actions)
- Read by your Python app at runtime (via `app/config.py`)
- Never stored in your code or Docker image

### Step 1: Check Your Allowed Azure Regions

Azure for Students has region restrictions. Check yours:

```bash
# Login to Azure
az login

# Check allowed regions
az policy assignment list --query "[?displayName=='Allowed resource deployment regions'].parameters" -o json
```

Common allowed regions for students: `eastus2`, `westus`, `westus2`, `northcentralus`, `southcentralus`

### Step 2: Create Azure Resources

**IMPORTANT:** Use a region from Step 1 (e.g., `eastus2`, NOT `eastus`)

```bash
# Set variables (update LOCATION to your allowed region!)
RESOURCE_GROUP=mini-lumina-rg
LOCATION=eastus2  # ← Use your allowed region
ACR_NAME=miniluminaacr$(date +%s)  # Unique name with timestamp
APP_SERVICE_PLAN=mini-lumina-plan
WEB_APP_NAME=mini-lumina-api-$(whoami)  # Unique name

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create container registry with admin enabled
az acr create --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME --sku Basic --location $LOCATION \
  --admin-enabled true

# Create app service plan (use F1 for free tier or B1 for better performance)
az appservice plan create --name $APP_SERVICE_PLAN \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --is-linux --sku B1

# Create web app
az webapp create --resource-group $RESOURCE_GROUP \
  --plan $APP_SERVICE_PLAN --name $WEB_APP_NAME \
  --deployment-container-image-name $ACR_NAME.azurecr.io/mini-lumina-api:latest

# Configure web app to use ACR
az webapp config container set \
  --name $WEB_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --docker-custom-image-name $ACR_NAME.azurecr.io/mini-lumina-api:latest \
  --docker-registry-server-url https://$ACR_NAME.azurecr.io

# Save these values - you'll need them!
echo "ACR_NAME: $ACR_NAME"
echo "WEB_APP_NAME: $WEB_APP_NAME"
```

### Step 3: Get Credentials for GitHub Secrets

Run these commands and **save the outputs**:

```bash
# Get ACR credentials
echo "ACR_LOGIN_SERVER:"
echo "$ACR_NAME.azurecr.io"

echo -e "\nACR_USERNAME:"
az acr credential show --name $ACR_NAME --query username -o tsv

echo -e "\nACR_PASSWORD:"
az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv

echo -e "\nAZURE_WEBAPP_PUBLISH_PROFILE:"
az webapp deployment list-publishing-profiles \
  --name $WEB_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --xml
```

### Step 4: Configure GitHub Secrets

1. Create a GitHub repository for this project
2. Go to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret** for each:

| Secret Name | Value | Where to Get |
|------------|-------|--------------|
| `ACR_LOGIN_SERVER` | e.g., `miniluminaacr123.azurecr.io` | From Step 3 output |
| `ACR_USERNAME` | e.g., `miniluminaacr123` | From Step 3 output |
| `ACR_PASSWORD` | Long password string | From Step 3 output |
| `AZURE_WEBAPP_NAME` | e.g., `mini-lumina-api-yourname` | From Step 2 |
| `AZURE_WEBAPP_PUBLISH_PROFILE` | **Entire XML content** | From Step 3 output (copy all) |
| `MONGO_URI` | `mongodb+srv://user:pass@...` | From your `.env` file |
| `OPENAI_API_KEY` | `sk-proj-...` | From your `.env` file |

**How These Work:**
- GitHub Actions reads these secrets during deployment
- Sets them as environment variables in Azure App Service
- Your Python app (`app/config.py`) reads them at runtime
- The app uses `OPENAI_API_KEY` to call OpenAI's external API

### Step 5: Push to GitHub and Deploy

```bash
# Initialize git (if not done)
git init
git add .
git commit -m "Initial deployment"

# Add GitHub remote (replace with your repo URL)
git remote add origin https://github.com/YOUR-USERNAME/mini-lumina.git

# Push to trigger deployment
git branch -M main
git push -u origin main
```

**What happens automatically:**
1. GitHub Actions runs tests (`pytest`)
2. Builds Docker image (in GitHub's cloud)
3. Pushes image to Azure Container Registry
4. Deploys to Azure App Service
5. Sets all environment variables

### Step 6: Monitor Deployment

**In GitHub:**
- Go to **Actions** tab
- Watch the workflow run
- Check for any errors in the logs

**In Azure:**
```bash
# Stream logs
az webapp log tail --name $WEB_APP_NAME --resource-group $RESOURCE_GROUP

# Check app status
az webapp show --name $WEB_APP_NAME --resource-group $RESOURCE_GROUP --query state -o tsv
```

### Step 7: Test Your Deployment

```bash
# Health check
curl https://$WEB_APP_NAME.azurewebsites.net/healthz

# Ask a question
curl -X POST https://$WEB_APP_NAME.azurewebsites.net/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is machine learning?", "top_k": 5}'
```

### Environment Variables Explained

**Set automatically by GitHub Actions workflow:**
- `MONGO_URI` - MongoDB connection (from GitHub Secret)
- `OPENAI_API_KEY` - OpenAI API key (from GitHub Secret)
- `MONGO_DB_NAME` - Database name (hardcoded: `lumina`)
- `MONGO_COLLECTION_NAME` - Collection name (hardcoded: `documents`)
- `EMBEDDING_MODEL` - OpenAI embedding model (hardcoded: `text-embedding-3-small`)
- `LLM_MODEL` - OpenAI LLM model (hardcoded: `gpt-4o-mini`)
- `LOG_LEVEL` - Logging level (hardcoded: `INFO`)
- `VECTOR_INDEX_NAME` - MongoDB vector index (hardcoded: `vector_index`)

**Note:** These are injected at runtime, NOT baked into the Docker image.

### Troubleshooting

**Region restriction error:**
```bash
# Check your allowed regions
az policy assignment list --query "[?displayName=='Allowed resource deployment regions'].parameters"

# Use one of the allowed regions in LOCATION variable
```

**ACR admin not enabled:**
```bash
az acr update -n $ACR_NAME --admin-enabled true
```

**Web app not starting:**
```bash
# Check logs
az webapp log tail --name $WEB_APP_NAME --resource-group $RESOURCE_GROUP

# Restart app
az webapp restart --name $WEB_APP_NAME --resource-group $RESOURCE_GROUP
```

**OpenAI API errors in production:**
- Verify `OPENAI_API_KEY` secret is set correctly in GitHub
- Check Azure App Service environment variables are set
- Review app logs for API errors

### Cost Management (Azure for Students)

**Estimated monthly costs:**
- Azure App Service B1: ~$13/month (or F1 Free tier)
- Azure Container Registry Basic: ~$5/month
- MongoDB Atlas M0: **$0** (free tier)
- OpenAI API: ~$5-20/month (depending on usage)

**Total: $18-38/month** (or $5-25 with free App Service)

**Your $100 credit lasts: 3-5 months**

**To save costs:**
- Use App Service F1 (free tier) instead of B1
- Use MongoDB Atlas M0 (free forever)
- Monitor OpenAI API usage in dashboard

## Model Evaluation

### Prepare Evaluation Dataset

Create `eval_dataset.csv`:

```csv
question,expected_doc_ids
What is the capital of France?,doc_1|doc_2
How does photosynthesis work?,doc_5|doc_12
```

### Run Evaluation

```bash
python -m app.eval --dataset eval_dataset.csv --output eval_report.json
```

This generates:
- Precision@K metrics
- Average retrieval latency
- Per-question retrieval scores

Sample output (`eval_report.json`):

```json
{
  "precision_at_1": 0.85,
  "precision_at_3": 0.72,
  "precision_at_5": 0.68,
  "avg_retrieval_latency_ms": 145.3,
  "total_questions": 20,
  "timestamp": "2025-01-15T10:30:00Z"
}
```

## API Endpoints

### Health Check
```bash
curl http://localhost:8000/healthz
```

### Ask Question
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is machine learning?",
    "top_k": 5
  }'
```

Response:
```json
{
  "answer": "Machine learning is...",
  "sources": [
    {
      "text": "...",
      "score": 0.92,
      "metadata": {...}
    }
  ],
  "latency_ms": 1250
}
```

## Testing Strategy

1. **Unit Tests**: Mock external services (OpenAI, MongoDB)
   ```bash
   pytest app/tests/test_chunking.py -v
   ```

2. **Integration Tests**: Test with real MongoDB (local or Atlas)
   ```bash
   pytest app/tests/test_retrieval.py -v --integration
   ```

3. **API Tests**: Test FastAPI endpoints
   ```bash
   pytest app/tests/test_api.py -v
   ```

4. **Load Testing**: Use locust or k6
   ```bash
   pip install locust
   locust -f load_test.py --host http://localhost:8000
   ```

## Monitoring and Logging

All logs are JSON-structured and include:
- `timestamp`
- `level`
- `event`
- `context` (request_id, user_id, etc.)

Example:
```json
{
  "timestamp": "2025-01-15T10:30:00.123Z",
  "level": "INFO",
  "event": "retrieval_completed",
  "context": {
    "question": "What is AI?",
    "num_results": 5,
    "latency_ms": 142
  }
}
```

## Troubleshooting

### MongoDB Connection Issues
- Check IP whitelist in Atlas
- Verify connection string format
- Test connection: `mongosh "mongodb+srv://..."`

### Vector Search Not Working
- Ensure index `vector_index` is built
- Verify embedding dimensions match (1536 for text-embedding-3-small)
- Check index status in Atlas UI

### Azure Deployment Fails
- Check container logs: `az webapp log tail --name $WEB_APP_NAME --resource-group $RESOURCE_GROUP`
- Verify environment variables are set
- Ensure ACR credentials are correct

## Performance Optimization

1. **Caching**: Add Redis for frequent queries
2. **Batch Processing**: Ingest multiple documents in parallel
3. **Connection Pooling**: Configure pymongo maxPoolSize
4. **CDN**: Use Azure CDN for static frontend assets

## Security Best Practices

- Store secrets in Azure Key Vault
- Enable managed identity for App Service
- Use private endpoints for MongoDB
- Implement rate limiting (e.g., slowapi)
- Add authentication/authorization (Azure AD, Auth0)

## Cost Estimates (Monthly)

- MongoDB Atlas M10: ~$60
- Azure App Service B1: ~$13
- Azure Container Registry Basic: ~$5
- OpenAI API (100K tokens/day): ~$20-50
- **Total**: ~$100-130/month

## License

MIT
