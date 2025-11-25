# Quick Start Guide

Get mini-lumina running in 5 minutes.

## Prerequisites

- Python 3.11+
- MongoDB Atlas account
- OpenAI API key

## Step 1: Clone and Setup

```bash
cd mini-lumina
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Step 2: Configure Environment

Create `.env` file:

```bash
cp .env.example .env
```

Edit `.env` and add your credentials:
- `MONGO_URI`: Your MongoDB Atlas connection string
- `OPENAI_API_KEY`: Your OpenAI API key

## Step 3: Create Vector Search Index

In MongoDB Atlas:
1. Go to your cluster → Search → Create Search Index
2. Choose JSON Editor
3. Paste this configuration:

```json
{
  "mappings": {
    "dynamic": true,
    "fields": {
      "embedding": {
        "type": "knnVector",
        "dimensions": 1536,
        "similarity": "cosine"
      }
    }
  }
}
```

4. Name: `vector_index`
5. Database: `lumina`, Collection: `documents`

## Step 4: Ingest Sample Documents

```bash
# Create a sample document
echo "Machine learning is a subset of artificial intelligence that enables systems to learn from data." > sample.txt

# Ingest it
python -m app.ingestion sample.txt
```

## Step 5: Run the Application

**Terminal 1 - Backend:**
```bash
uvicorn app.main:app --reload
```

**Terminal 2 - Frontend:**
```bash
streamlit run streamlit_app/app.py
```

## Step 6: Test It

1. Open http://localhost:8501
2. Ask: "What is machine learning?"
3. See the magic! ✨

## Using Docker (Alternative)

```bash
# Build and run
docker-compose up --build

# Access
# Backend: http://localhost:8000
# Frontend: http://localhost:8501
```

## Troubleshooting

**MongoDB connection fails:**
- Check IP whitelist in Atlas
- Verify connection string format

**No results returned:**
- Ensure vector index is built (check Atlas UI)
- Verify documents are ingested: check MongoDB collection

**API errors:**
- Check OpenAI API key is valid
- Verify you have API credits

## Next Steps

- Read full [README.md](README.md) for deployment
- Ingest your own documents
- Run evaluation: `python -m app.eval`
- Deploy to Azure (see README)
