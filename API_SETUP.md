# FastAPI Backend Setup

## Local Testing

```bash
# Install dependencies
pip install fastapi uvicorn

# Run server
uvicorn main:app --reload

# Test at http://localhost:8000/docs
```

## Test Request

```json
{
  "query": "I want to build muscle in my legs",
  "user_profile": {
    "age": 24,
    "sex": "Male",
    "weight_kg": 75.5,
    "height_cm": 178
  }
}
```

## Deployment Options

### Render (Free Tier)
1. Push to GitHub
2. Connect Render to repo
3. Set environment variables
4. Deploy

### Railway (Free Tier)
1. Push to GitHub
2. Connect Railway to repo
3. Set environment variables
4. Deploy

## Environment Variables

```bash
ELASTICSEARCH_URL=https://...
ELASTICSEARCH_API_KEY=...
OPENAI_API_KEY=sk-...
```

## Endpoints

- `GET /health` - Health check
- `POST /api/recommend` - Main RAG endpoint
- `GET /docs` - Interactive API docs
