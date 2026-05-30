# RAG Health & Fitness POC

Simple proof-of-concept demonstrating Retrieval-Augmented Generation (RAG) for fitness recommendations.

## Setup

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Configure environment:**
The `.env` file is already configured with your API keys.

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
2. **query.py** - Takes your prompt, searches Elasticsearch with k-NN, calls Gemini API with retrieved context

## Stack

- **Elasticsearch Cloud** - Vector store
- **sentence-transformers** - Embeddings (all-MiniLM-L6-v2)
- **Google Gemini 1.5 Flash** - LLM

## Troubleshooting

**"Error connecting to Elasticsearch"**
- Check your `.env` file has correct ELASTICSEARCH_URL and ELASTICSEARCH_API_KEY

**"Error calling Gemini API"**
- Check your `.env` file has correct GOOGLE_GEMINI_API_KEY

**"No results found"**
- Run `python crawler.py` first to index data
