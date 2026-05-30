# Design Document: RAG Health & Fitness POC

## Overview

This is a **simple proof-of-concept (POC)** for a school project demonstrating Retrieval-Augmented Generation (RAG). The system consists of two Python scripts:

1. **crawler.py** - Fetches exercise/recipe data, generates embeddings, and indexes into Elasticsearch
2. **query.py** - Takes a user prompt, searches Elasticsearch, and generates a response using Google Gemini

**Technology Stack:**
- Python 3.10+
- Elasticsearch Cloud (vector store)
- sentence-transformers (embeddings)
- Google Gemini API (LLM)

**Scope:** Minimal viable product for educational purposes. No web interface, no production deployment.

## Architecture

### System Components

```
┌─────────────┐
│   User      │
└──────┬──────┘
       │
       │ 1. Run crawler.py (one-time setup)
       ├──────────────────────────────────┐
       │                                  │
       │                                  ▼
       │                         ┌────────────────┐
       │                         │  Elasticsearch │
       │                         │  Cloud         │
       │                         │  (Vector Store)│
       │                         └────────────────┘
       │                                  ▲
       │ 2. Run query.py "prompt"         │
       ├──────────────────────────────────┤
       │                                  │
       ▼                                  │
┌──────────────┐                         │
│  query.py    │─────search──────────────┘
│              │
│  - Embed     │
│  - Search    │
│  - Generate  │
└──────┬───────┘
       │
       │ 3. Call Gemini API
       ▼
┌──────────────┐
│ Google Gemini│
│ 1.5 Flash    │
└──────┬───────┘
       │
       │ 4. Print response
       ▼
┌──────────────┐
│   Console    │
└──────────────┘
```

### Data Flow

**Setup Phase (crawler.py):**
1. Fetch 50+ exercises from public API/dataset
2. Fetch 50+ recipes from public source
3. Generate embeddings using sentence-transformers
4. Create Elasticsearch indices with proper mappings
5. Bulk index documents

**Query Phase (query.py):**
1. User runs: `python query.py "I want to build muscle"`
2. Generate embedding for the prompt
3. Search Elasticsearch for top 3 exercises and recipes
4. Construct prompt with retrieved context
5. Call Gemini API
6. Print response to console

## Components and Interfaces

### crawler.py

**Purpose:** One-time data ingestion script

**Functions:**
```python
def fetch_exercises() -> List[Dict]:
    """Fetch exercise data from public API"""
    
def fetch_recipes() -> List[Dict]:
    """Fetch recipe data from public source"""
    
def generate_embedding(text: str) -> List[float]:
    """Generate 384-dim embedding using sentence-transformers"""
    
def create_indices(es_client):
    """Create Elasticsearch indices with vector mappings"""
    
def bulk_index(es_client, index_name: str, documents: List[Dict]):
    """Bulk index documents into Elasticsearch"""
    
def main():
    """Main execution: fetch, embed, index"""
```

**Usage:**
```bash
python crawler.py
```

**Output:**
```
Fetching exercises...
Fetched 50 exercises
Generating embeddings...
Creating indices...
Indexing exercises...
Indexed 50 exercises
Fetching recipes...
Fetched 50 recipes
Indexing recipes...
Indexed 50 recipes
Done!
```

### query.py

**Purpose:** Interactive query script

**Functions:**
```python
def generate_embedding(text: str) -> List[float]:
    """Generate embedding for query"""
    
def search_elasticsearch(es_client, query_embedding: List[float]) -> Dict:
    """Search for top 3 exercises and recipes"""
    
def build_prompt(user_query: str, exercises: List, recipes: List) -> str:
    """Construct RAG prompt with context"""
    
def call_gemini(prompt: str) -> str:
    """Call Gemini API and return response"""
    
def main(user_query: str):
    """Main execution: embed, search, generate"""
```

**Usage:**
```bash
python query.py "I want to build muscle and lose fat"
```

**Output:**
```
Searching for relevant exercises and recipes...
Found 3 exercises, 3 recipes
Generating response...

Based on your goal to build muscle and lose fat, here's a plan:

[Gemini's response with exercises and recipes]
```

## Data Models

### Elasticsearch Indices

**exercises index:**
```json
{
  "mappings": {
    "properties": {
      "name": { "type": "text" },
      "description": { "type": "text" },
      "embedding": {
        "type": "dense_vector",
        "dims": 384,
        "similarity": "cosine"
      }
    }
  }
}
```

**recipes index:**
```json
{
  "mappings": {
    "properties": {
      "name": { "type": "text" },
      "ingredients": { "type": "text" },
      "embedding": {
        "type": "dense_vector",
        "dims": 384,
        "similarity": "cosine"
      }
    }
  }
}
```

### Python Data Structures

```python
# Exercise document
{
    "name": "Push-ups",
    "description": "Upper body exercise targeting chest and triceps",
    "embedding": [0.123, -0.456, ...]  # 384 dimensions
}

# Recipe document
{
    "name": "Protein Smoothie",
    "ingredients": "banana, protein powder, milk, peanut butter",
    "embedding": [0.789, -0.012, ...]  # 384 dimensions
}
```

## Environment Variables

Required in `.env` file:

```bash
ELASTICSEARCH_URL=https://your-deployment.es.cloud.es.io:443
ELASTICSEARCH_API_KEY=your_api_key_here
GOOGLE_GEMINI_API_KEY=your_gemini_key_here
```

## Dependencies

**requirements.txt:**
```
elasticsearch==8.11.0
sentence-transformers==2.2.2
google-generativeai==0.3.0
python-dotenv==1.0.0
requests==2.31.0
```

**Installation:**
```bash
pip install -r requirements.txt
```

## Correctness Properties

**Property-based testing is not applicable to this feature.**

This is a simple POC script that integrates external services (Elasticsearch, Gemini API). Testing will be manual only.

## Error Handling

### Basic Error Handling Strategy

**Elasticsearch Connection Errors:**
```python
try:
    es_client.search(...)
except Exception as e:
    print(f"Error connecting to Elasticsearch: {e}")
    sys.exit(1)
```

**Gemini API Errors:**
```python
try:
    response = model.generate_content(prompt)
except Exception as e:
    print(f"Error calling Gemini API: {e}")
    sys.exit(1)
```

**Embedding Generation Errors:**
```python
try:
    embedding = model.encode(text)
except Exception as e:
    print(f"Error generating embedding: {e}")
    sys.exit(1)
```

**Missing Environment Variables:**
```python
if not os.getenv('ELASTICSEARCH_URL'):
    print("Error: ELASTICSEARCH_URL not set in .env file")
    sys.exit(1)
```

## Testing Strategy

**Manual Testing Only** - This is a POC, no automated tests required.

**Test Checklist:**
1. ✅ Run crawler.py - verify data is indexed
2. ✅ Check Elasticsearch - verify indices exist with documents
3. ✅ Run query.py with sample prompt - verify response is generated
4. ✅ Try different prompts - verify relevant results are retrieved

**Verification Commands:**
```bash
# Check if indices exist
curl -X GET "$ELASTICSEARCH_URL/_cat/indices?v" \
  -H "Authorization: ApiKey $ELASTICSEARCH_API_KEY"

# Count documents
curl -X GET "$ELASTICSEARCH_URL/exercises/_count" \
  -H "Authorization: ApiKey $ELASTICSEARCH_API_KEY"
```
