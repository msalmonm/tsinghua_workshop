# RAG Health & Fitness POC

Simple proof-of-concept demonstrating Retrieval-Augmented Generation (RAG) for fitness recommendations using OpenAI API.

## Setup

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Configure environment:**
Create a `.env` file in the project root with the following variables:

```bash
# OpenMP Configuration (fix for duplicate library warning)
KMP_DUPLICATE_LIB_OK=TRUE

# Elasticsearch Configuration
# Get your credentials from: https://cloud.elastic.co/
ELASTICSEARCH_URL=https://your-deployment-id.region.gcp.cloud.es.io:443
ELASTICSEARCH_API_KEY=your_elasticsearch_api_key_here

# OpenAI API Configuration (RECOMMENDED)
# Get your API key at: https://platform.openai.com/api-keys
# New accounts get $5 free credit (~20,000 queries)
OPENAI_API_KEY=sk-your-openai-key-here
```

## Usage

### Step 1: Run the crawler (one-time setup)
```bash
python crawler.py
```

This will:
- Fetch 120 exercises from GitHub's free-exercise-db
- Fetch ~140 recipes from TheMealDB API
- Generate 384-dimensional embeddings
- Index everything into Elasticsearch (~30 seconds)

### Step 2: Query the system
```bash
python query.py "I want to build muscle"
```

Examples:
```bash
python query.py "I want to lose weight"
python query.py "I need a high protein meal plan"
python query.py "What exercises for abs?"
python query.py "I'm a beginner looking to get stronger"
```

## How it works

```
User Query → Embedding → Elasticsearch (k-NN) → Top 3 Exercises + Top 3 Recipes
                                                           ↓
                                                    OpenAI API
                                                           ↓
                                              Personalized Response
```

1. **crawler.py** - Fetches real fitness data, generates embeddings, indexes to Elasticsearch
2. **query.py** - Converts query to embedding, searches Elasticsearch, calls OpenAI with context

## Stack

- **Elasticsearch Cloud** - Vector database with k-NN search
- **sentence-transformers** - Embeddings (all-MiniLM-L6-v2, 384-dim)
- **OpenAI API** - LLM (gpt-4o-mini or gpt-3.5-turbo)
- **GitHub + TheMealDB** - Real exercise and recipe data

## Troubleshooting

**"Error connecting to Elasticsearch"**
- Check your `.env` file has correct ELASTICSEARCH_URL and ELASTICSEARCH_API_KEY
- Test connection: `curl -H "Authorization: ApiKey $ELASTICSEARCH_API_KEY" $ELASTICSEARCH_URL`

**"Invalid API key" (OpenAI)**
- Verify your key at: https://platform.openai.com/api-keys
- Ensure it starts with `sk-`
- Check for extra spaces in `.env` file

**"Rate limit exceeded" (OpenAI)**
- Wait 60 seconds and retry
- Check usage at: https://platform.openai.com/usage
- System automatically falls back to template response

**"No results found"**
- Run `python crawler.py` first to index data
- Verify indices exist in Elasticsearch

**Network issues**
- OpenAI has better connectivity than Hugging Face
- System includes fallback response generator
- Check firewall/proxy settings if needed

## Features

✅ **Semantic Vector Search** - 384-dimensional embeddings for intelligent retrieval  
✅ **High-Quality Responses** - OpenAI GPT-4o-mini for natural, helpful advice  
✅ **Real Data** - 120 exercises + 140 recipes from public APIs  
✅ **Fast** - 2-5 second response time  
✅ **Robust Fallback** - Works without API key using template responses  
✅ **Cost Effective** - $0.00024 per query, $5 free credit for new accounts

## Documentation

- **[CRAWLER_DOCUMENTATION.md](CRAWLER_DOCUMENTATION.md)** - Complete crawler architecture and data sources
- **[OPENAI_MIGRATION.md](OPENAI_MIGRATION.md)** - OpenAI API integration guide and design decisions
- **[SETUP.md](SETUP.md)** - Detailed setup instructions

## Alternative: Local LLM

If you prefer to run everything locally without API keys:

```bash
# Install Ollama: https://ollama.ai/download
ollama run llama3.2:3b

# Use local version
python query_local.py "I want to build muscle"
```

## Cost Analysis

**OpenAI (gpt-4o-mini):**
- Input: $0.15 per 1M tokens
- Output: $0.60 per 1M tokens
- **~$0.00024 per query**
- **$5 free credit = ~20,000 queries**

Perfect for development, testing, and small-scale production.
