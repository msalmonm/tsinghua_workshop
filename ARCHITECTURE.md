# RAG System Architecture

## Data Flow

```
┌─────────────┐
│ crawler.py  │ (One-time setup)
└──────┬──────┘
       │
       ├─► GitHub API → 120 exercises
       ├─► TheMealDB API → ~140 recipes
       │
       ├─► SentenceTransformer (all-MiniLM-L6-v2)
       │   └─► 384-dim embeddings from search_context
       │
       └─► Elasticsearch (bulk index)
           ├─► exercises index
           └─► recipes index

┌─────────────┐
│  query.py   │ (Runtime)
└──────┬──────┘
       │
       ├─► User query → SentenceTransformer → 384-dim embedding
       │
       ├─► Elasticsearch k-NN search
       │   ├─► Top 3 exercises (cosine similarity)
       │   └─► Top 3 recipes (cosine similarity)
       │
       ├─► OpenAI Chat Completions API
       │   ├─► System: Role definition + rules
       │   ├─► User: Query + retrieved context
       │   └─► Models: gpt-4o-mini → gpt-3.5-turbo
       │
       └─► Response (or fallback if API fails)
```

## Shared Components

**Embedding Model:** `sentence-transformers/all-MiniLM-L6-v2`
- Dims: 384
- Used by: Both crawler (indexing) and query (search)
- Ensures semantic consistency

**Elasticsearch Schema:**
```json
{
  "name": "text",
  "category": "keyword",
  "search_context": "text",
  "embedding": {
    "type": "dense_vector",
    "dims": 384,
    "similarity": "cosine"
  }
}
```

**search_context Format:**
- Exercises: `{name}. Level: {level}. Equipment: {equipment}. Muscle: {muscles}. Category: {category}. Description: {description}`
- Recipes: `{name}. Category: {category}. Ingredients: {ingredients}. Instructions: {instructions}`

## Key Integration Points

1. **Same embedding model** ensures query vectors match indexed vectors
2. **search_context field** provides rich semantic context for both indexing and retrieval
3. **Cosine similarity** measures semantic closeness (angle between vectors)
4. **k-NN search** with k=3, num_candidates=50 balances speed/accuracy

## Execution

**Setup (once):**
```bash
python crawler.py  # ~30 seconds
```

**Query (runtime):**
```bash
python query.py "I want to build muscle"  # ~3-5 seconds
```

## Dependencies

- `sentence-transformers` - Embedding generation
- `elasticsearch` - Vector database
- `requests` - API calls (data fetching, OpenAI)
- `python-dotenv` - Config management

## Configuration (.env)

```bash
ELASTICSEARCH_URL=https://...
ELASTICSEARCH_API_KEY=...
OPENAI_API_KEY=sk-...
```
