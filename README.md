# RAG Health & Fitness POC

Simple proof-of-concept demonstrating Retrieval-Augmented Generation (RAG) for fitness recommendations.

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

# Hugging Face API Configuration (OPTIONAL)
# Get your free API key at: https://huggingface.co/settings/tokens
# The system works without this key but with rate limits
HUGGINGFACE_API_KEY=your_huggingface_token_here
```

## Usage

### Step 1: Run the crawler (one-time setup)
```bash
python crawler.py
```

This will:
- Fetch exercises from Wger API
- Create sample recipes
- Generate embeddings
- Index everything into Elasticsearch

### Step 2: Query the system
```bash
python query.py "I want to build muscle"
```

Examples:
```bash
python query.py "I want to lose weight"
python query.py "I need a high protein meal plan"
python query.py "What exercises for abs?"
```

## How it works

1. **crawler.py** - Fetches data, generates 384-dim embeddings (sentence-transformers), indexes to Elasticsearch
2. **query.py** - Takes your prompt, searches Elasticsearch with k-NN, calls Hugging Face Inference API (Mistral-7B) with retrieved context

## Stack

- **Elasticsearch Cloud** - Vector store
- **sentence-transformers** - Embeddings (all-MiniLM-L6-v2)
- **Hugging Face Inference API** - LLM (Mistral-7B-Instruct-v0.2) - FREE!

## Troubleshooting

**"Error connecting to Elasticsearch"**
- Check your `.env` file has correct ELASTICSEARCH_URL and ELASTICSEARCH_API_KEY

**"Model is loading"**
- Hugging Face models may take 20 seconds to load on first request (cold start)
- The script will automatically wait and retry

**"No results found"**
- Run `python crawler.py` first to index data

**Rate limits**
- Without API key: ~1000 requests/day
- With free API key: Higher limits
- Get your free key at: https://huggingface.co/settings/tokens

## Features

✅ **Semantic Vector Search** - Uses 384-dimensional embeddings for intelligent content retrieval  
✅ **Personalized Responses** - Context-aware recommendations based on retrieved exercises and recipes  
✅ **Robust Fallback** - Works offline with intelligent local response generation  
✅ **Free & Open Source** - No paid API keys required
