# RAG Health & Fitness POC - Crawler Documentation

## Overview

The `crawler.py` script is a data ingestion pipeline that fetches fitness exercises and recipes from public APIs, generates semantic embeddings, and indexes them into Elasticsearch for vector similarity search in a RAG (Retrieval-Augmented Generation) system.

---

## Architecture

```
┌─────────────────┐
│  Data Sources   │
├─────────────────┤
│ • GitHub JSON   │ (Exercises)
│ • TheMealDB API │ (Recipes)
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│  Embedding Generation   │
│  (SentenceTransformer)  │
│  384-dim vectors        │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│   Elasticsearch         │
│   Vector Database       │
│   • exercises index     │
│   • recipes index       │
└─────────────────────────┘
```

---

## Data Sources

### 1. Exercises - GitHub Open Source Database

**Source:** `https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/dist/exercises.json`

**Why this source?**
- ✅ Static JSON dump (no rate limits, no authentication)
- ✅ 800+ exercises with rich metadata
- ✅ Highly reliable (GitHub CDN)
- ✅ Zero API failures

**Data Structure:**
```json
{
  "name": "Barbell Squat",
  "category": "strength",
  "level": "intermediate",
  "equipment": "barbell",
  "primaryMuscles": ["quadriceps", "glutes"],
  "instructions": [
    "Step 1: Position barbell on upper back",
    "Step 2: Lower body by bending knees..."
  ]
}
```

**Processing:**
- Takes first 120 exercises (for MVP speed)
- Combines all fields into rich `search_context`
- Generates unique ID: `ex_gh_{index}`

### 2. Recipes - TheMealDB API

**Source:** `https://www.themealdb.com/api/json/v1/1/search.php?f={letter}`

**Why this source?**
- ✅ Free public API (no authentication required)
- ✅ Rich recipe data with ingredients and instructions
- ✅ Well-maintained and reliable

**Fetching Strategy:**
- Searches by first letter: `['a', 'b', 'c', 's']`
- Fetches ~100-150 recipes total
- Extracts up to 20 ingredients per recipe

**Data Structure:**
```json
{
  "idMeal": "52772",
  "strMeal": "Teriyaki Chicken Casserole",
  "strCategory": "Chicken",
  "strIngredient1": "soy sauce",
  "strMeasure1": "3/4 cup",
  "strInstructions": "Preheat oven to 350°..."
}
```

**Processing:**
- Combines ingredients with measurements
- Truncates instructions to 800 chars
- Generates unique ID: `rec_{idMeal}`

---

## Embedding Generation

### Model: `sentence-transformers/all-MiniLM-L6-v2`

**Specifications:**
- **Dimensions:** 384
- **Max Sequence Length:** 256 tokens
- **Model Size:** ~80MB
- **Speed:** ~1000 sentences/sec on CPU

**Why this model?**
- ✅ Lightweight and fast
- ✅ Good semantic understanding
- ✅ Works offline after first download
- ✅ Optimized for semantic search

### Search Context Construction

Each document creates a rich semantic context:

**Exercise Example:**
```
"Barbell Squat. Level: intermediate. Equipment: barbell. 
Muscle Group: quadriceps, glutes. Category: Strength. 
Description: Position barbell on upper back. Lower body by bending knees..."
```

**Recipe Example:**
```
"Teriyaki Chicken Casserole. Category: Chicken. 
Ingredients: 3/4 cup soy sauce, 1/2 cup water, 1/4 cup brown sugar... 
Instructions: Preheat oven to 350°..."
```

This rich context ensures better semantic matching during RAG queries.

---

## Elasticsearch Schema

### Index Mapping

Both `exercises` and `recipes` indices use the same schema:

```json
{
  "mappings": {
    "properties": {
      "name": {
        "type": "text"
      },
      "category": {
        "type": "keyword"
      },
      "search_context": {
        "type": "text"
      },
      "embedding": {
        "type": "dense_vector",
        "dims": 384,
        "index": true,
        "similarity": "cosine"
      }
    }
  }
}
```

**Field Descriptions:**

| Field | Type | Purpose |
|-------|------|---------|
| `name` | text | Exercise/recipe name (searchable) |
| `category` | keyword | Exact match filtering (e.g., "Strength", "Chicken") |
| `search_context` | text | Full semantic context for embedding |
| `embedding` | dense_vector | 384-dim vector for KNN search |

**Vector Configuration:**
- **Similarity:** Cosine (measures angle between vectors)
- **Indexed:** True (enables fast approximate KNN)
- **Dimensions:** 384 (matches embedding model)

---

## Workflow

### Step-by-Step Execution

```python
# 1. Initialize
load_dotenv()                    # Load .env configuration
model = SentenceTransformer()    # Load embedding model
es_client = Elasticsearch()      # Connect to Elasticsearch

# 2. Fetch Data
exercises = fetch_exercises()    # ~120 exercises from GitHub
recipes = fetch_recipes()        # ~100-150 recipes from TheMealDB

# 3. Reset Indices
create_indices(es_client)        # Delete old indices, create new ones

# 4. Generate Embeddings & Index
bulk_index(es_client, "exercises", exercises)
bulk_index(es_client, "recipes", recipes)
```

### Bulk Indexing Process

```python
for doc in documents:
    # 1. Generate embedding from search_context
    embedding = model.encode(doc['search_context'])
    
    # 2. Add embedding to document
    doc['embedding'] = embedding.tolist()
    
    # 3. Prepare bulk action
    action = {
        "_index": index_name,
        "_id": doc['id'],
        "_source": doc
    }
    
# 4. Bulk insert all documents
helpers.bulk(es_client, actions)
```

---

## Key Features

### 1. **Idempotent Execution**
- Deletes existing indices before creating new ones
- Safe to run multiple times without duplicates

### 2. **Error Handling**
- Validates environment variables
- Graceful failure on API errors
- Continues processing if one data source fails

### 3. **Performance Optimizations**
- Bulk indexing (not one-by-one)
- Limits exercise count to 120 for MVP speed
- Truncates long text fields (800-1000 chars)

### 4. **Rich Semantic Context**
- Combines multiple fields into `search_context`
- Includes metadata (category, level, equipment)
- Optimized for RAG retrieval quality

---

## Configuration

### Required Environment Variables

```bash
# .env file
ELASTICSEARCH_URL=https://your-cluster.es.io:443
ELASTICSEARCH_API_KEY=your_api_key_here
```

### Optional Tuning

**Fetch more exercises:**
```python
for i, item in enumerate(data[:120]):  # Change 120 to 500
```

**Fetch more recipe letters:**
```python
letters_to_fetch = ['a', 'b', 'c', 's']  # Add more letters
```

**Adjust text truncation:**
```python
'description': description[:800],  # Increase limit
'search_context': search_context[:1000]  # Increase limit
```

---

## Usage

### Basic Execution

```bash
python crawler.py
```

### Expected Output

```
============================================================
RAG Health & Fitness POC - Data Crawler
============================================================
Loading embedding model...
Model loaded successfully
✓ Connected to Elasticsearch

Fetching exercises from public Open Source database...
Fetched 120 exercises from public database

Crawling recipes from TheMealDB...
Fetched 142 recipes from API

Creating Elasticsearch indices...
Exercises index already exists, deleting...
Created exercises index
Recipes index already exists, deleting...
Created recipes index

Generating embeddings and bulk indexing 120 into exercises...
Successfully indexed 120 documents into exercises

Generating embeddings and bulk indexing 142 into recipes...
Successfully indexed 142 documents into recipes

============================================================
✓ Crawler completed successfully!
============================================================
```

---

## Data Quality

### Exercises Dataset Quality

| Metric | Value |
|--------|-------|
| Total Available | 800+ |
| Indexed (MVP) | 120 |
| Fields per Exercise | 8+ |
| Instruction Steps | 3-10 per exercise |
| Muscle Groups | 1-3 per exercise |

### Recipes Dataset Quality

| Metric | Value |
|--------|-------|
| Total Fetched | ~140 |
| Ingredients per Recipe | 5-15 |
| Instruction Length | 200-800 chars |
| Categories | 10+ (Chicken, Beef, Vegetarian, etc.) |

---

## Integration with RAG Pipeline

### How the Crawler Fits

```
┌──────────────┐
│  crawler.py  │  ← YOU ARE HERE
└──────┬───────┘
       │ Indexes data with embeddings
       ▼
┌──────────────────┐
│  Elasticsearch   │
│  Vector Database │
└──────┬───────────┘
       │ KNN Search
       ▼
┌──────────────┐
│   query.py   │  ← Retrieves relevant context
└──────┬───────┘
       │ Builds prompt
       ▼
┌──────────────┐
│  LLM (HF/Ollama) │  ← Generates response
└──────────────┘
```

### Query Flow Example

1. **User Query:** "I want to build muscle"
2. **Embedding:** Convert query to 384-dim vector
3. **KNN Search:** Find top 3 exercises + top 3 recipes
4. **Context:** Retrieved documents become LLM context
5. **Generation:** LLM generates personalized response

---

## Troubleshooting

### Issue: "Error connecting to Elasticsearch"

**Solution:**
```bash
# Verify credentials in .env
echo $ELASTICSEARCH_URL
echo $ELASTICSEARCH_API_KEY

# Test connection
curl -H "Authorization: ApiKey $ELASTICSEARCH_API_KEY" $ELASTICSEARCH_URL
```

### Issue: "Error fetching exercises"

**Possible Causes:**
- GitHub API rate limit (unlikely with raw.githubusercontent.com)
- Network connectivity issues
- Firewall blocking GitHub

**Solution:**
```bash
# Test direct access
curl https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/dist/exercises.json
```

### Issue: "Error fetching recipes"

**Possible Causes:**
- TheMealDB API down (rare)
- Network connectivity issues

**Solution:**
```bash
# Test API access
curl https://www.themealdb.com/api/json/v1/1/search.php?f=a
```

### Issue: "Model loading slow"

**First Run:** Downloads ~80MB model from Hugging Face
**Subsequent Runs:** Loads from cache (~2 seconds)

**Cache Location:**
- Windows: `C:\Users\{username}\.cache\huggingface\`
- Linux/Mac: `~/.cache/huggingface/`

---

## Performance Metrics

### Execution Time (Typical)

| Phase | Time |
|-------|------|
| Model Loading | 2-5 seconds |
| Fetch Exercises | 1-2 seconds |
| Fetch Recipes | 3-5 seconds |
| Create Indices | 1 second |
| Generate Embeddings (120 exercises) | 5-10 seconds |
| Generate Embeddings (140 recipes) | 5-10 seconds |
| Bulk Indexing | 2-3 seconds |
| **Total** | **~20-35 seconds** |

### Resource Usage

- **Memory:** ~500MB (embedding model + data)
- **CPU:** Moderate (embedding generation)
- **Network:** ~5MB download (data fetching)
- **Disk:** ~80MB (cached model)

---

## Future Enhancements

### Potential Improvements

1. **Incremental Updates**
   - Check for new data instead of full reindex
   - Use document versioning

2. **More Data Sources**
   - Nutrition databases (USDA FoodData Central)
   - Workout plans (Bodybuilding.com)
   - Health articles (PubMed)

3. **Better Embeddings**
   - Fine-tune model on fitness domain
   - Use larger models (768-dim)
   - Multi-lingual support

4. **Metadata Enrichment**
   - Add difficulty scores
   - Calculate nutritional macros
   - Tag allergens and dietary restrictions

5. **Monitoring**
   - Log indexing metrics
   - Track data freshness
   - Alert on API failures

---

## Related Files

- **`query.py`** - RAG query script that searches indexed data
- **`query_local.py`** - Local LLM version (Ollama)
- **`.env`** - Configuration file with credentials
- **`requirements.txt`** - Python dependencies

---

## Dependencies

```txt
python-dotenv==1.0.0
elasticsearch==8.11.0
sentence-transformers==2.2.2
requests==2.31.0
```

---

## License & Attribution

### Data Sources

- **Exercises:** [free-exercise-db](https://github.com/yuhonas/free-exercise-db) (Public Domain)
- **Recipes:** [TheMealDB](https://www.themealdb.com/) (Free API)

### Embedding Model

- **Model:** [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
- **License:** Apache 2.0

---

## Summary

The crawler is a robust, production-ready data ingestion pipeline that:

✅ Fetches real-world fitness and nutrition data  
✅ Generates high-quality semantic embeddings  
✅ Indexes efficiently into Elasticsearch  
✅ Handles errors gracefully  
✅ Runs in ~30 seconds  
✅ Supports the RAG query pipeline  

It's the foundation of the RAG system, ensuring high-quality retrieval for personalized fitness recommendations.
