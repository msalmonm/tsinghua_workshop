# Implementation Plan: RAG Health & Fitness POC

## Overview

This implementation plan breaks down the RAG Health & Fitness POC into discrete coding tasks. The system consists of two simple Python scripts:

1. **crawler.py** - Fetches exercise/recipe data, generates embeddings, and indexes into Elasticsearch
2. **query.py** - Takes a user prompt, searches Elasticsearch, and generates a response using Google Gemini

This is a minimal proof-of-concept for educational purposes with no web frontend or complex architecture.

## Tasks

- [ ] 1. Set up project structure and dependencies
  - Create requirements.txt with dependencies: elasticsearch, sentence-transformers, google-generativeai, python-dotenv, requests
  - Create .env file with placeholders for ELASTICSEARCH_URL, ELASTICSEARCH_API_KEY, GOOGLE_GEMINI_API_KEY
  - Create project directory structure (root level scripts)
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [ ] 2. Implement crawler.py - Data fetching and indexing
  - [ ] 2.1 Implement exercise data fetching
    - Create fetch_exercises() function to retrieve at least 50 exercises from a public API or dataset
    - Parse and normalize exercise data (name, description fields)
    - Print progress to console
    - _Requirements: 1.1, 1.6_

  - [ ] 2.2 Implement recipe data fetching
    - Create fetch_recipes() function to retrieve at least 50 recipes from a public source
    - Parse and normalize recipe data (name, ingredients fields)
    - Print progress to console
    - _Requirements: 1.2, 1.6_

  - [ ] 2.3 Implement embedding generation
    - Load sentence-transformers model (all-MiniLM-L6-v2)
    - Create generate_embedding() function that returns 384-dimensional vectors
    - Handle model initialization errors with clear error messages
    - _Requirements: 1.3, 5.3_

  - [ ] 2.4 Implement Elasticsearch index creation
    - Create create_indices() function to set up exercises and recipes indices
    - Define mappings with name, description/ingredients (text), and embedding (dense_vector, 384 dims, cosine similarity)
    - Ensure indices support k-NN search
    - Handle connection errors with clear error messages
    - _Requirements: 1.4, 2.1, 2.2, 2.3, 2.4, 5.1_

  - [ ] 2.5 Implement bulk indexing
    - Create bulk_index() function to index documents with embeddings
    - Generate embeddings for all exercises and recipes
    - Bulk index documents into Elasticsearch
    - Print progress to console (e.g., "Indexed 50 exercises")
    - _Requirements: 1.5, 1.6_

  - [ ] 2.6 Wire crawler.py main() function
    - Load environment variables from .env file
    - Validate required environment variables (ELASTICSEARCH_URL, ELASTICSEARCH_API_KEY)
    - Call fetch_exercises(), fetch_recipes(), create_indices(), bulk_index() in sequence
    - Print completion message
    - Handle missing environment variables with clear error messages
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 4.1, 4.2, 4.4_

- [ ] 3. Checkpoint - Verify crawler.py works
  - Run crawler.py and verify data is indexed into Elasticsearch
  - Check Elasticsearch indices exist with correct document counts

- [ ] 4. Implement query.py - Query and response generation
  - [ ] 4.1 Implement query embedding generation
    - Load sentence-transformers model (all-MiniLM-L6-v2)
    - Create generate_embedding() function for user query
    - Handle model initialization errors with clear error messages
    - _Requirements: 3.2, 5.3_

  - [ ] 4.2 Implement Elasticsearch vector search
    - Create search_elasticsearch() function that accepts query embedding
    - Execute k-NN search for top 3 exercises and top 3 recipes
    - Return structured results with name and description/ingredients
    - Handle connection errors with clear error messages
    - _Requirements: 3.3, 5.1_

  - [ ] 4.3 Implement RAG prompt construction
    - Create build_prompt() function that accepts user query, exercises, and recipes
    - Format prompt with user query and retrieved context
    - Include instructions for Gemini to use only provided context
    - _Requirements: 3.4_

  - [ ] 4.4 Implement Gemini API integration
    - Initialize Google Generative AI SDK with API key
    - Create call_gemini() function that sends prompt and returns response
    - Configure Gemini 1.5 Flash model
    - Handle API errors with clear error messages
    - _Requirements: 3.5, 5.2_

  - [ ] 4.5 Wire query.py main() function
    - Accept user query as command-line argument
    - Load environment variables from .env file
    - Validate required environment variables (ELASTICSEARCH_URL, ELASTICSEARCH_API_KEY, GOOGLE_GEMINI_API_KEY)
    - Call generate_embedding(), search_elasticsearch(), build_prompt(), call_gemini() in sequence
    - Print response to console
    - Handle missing environment variables with clear error messages
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.1, 4.2, 4.3, 4.4_

- [ ] 5. Final checkpoint - Verify end-to-end workflow
  - Run query.py with sample prompts and verify responses are generated
  - Test error handling for missing environment variables
  - Test error handling for Elasticsearch connection failures
  - Test error handling for Gemini API failures

## Notes

- This is a simple POC with no automated tests - manual testing only
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Both scripts use Python 3.10+ as specified in the design
- Environment variables must be configured in .env file before running scripts
- crawler.py must be run once before query.py can be used
- No property-based testing per the design document's testing strategy

## Task Dependency Graph

```json
{
  "waves": [
    {
      "id": 0,
      "tasks": ["1"]
    },
    {
      "id": 1,
      "tasks": ["2.1", "2.2", "2.3"]
    },
    {
      "id": 2,
      "tasks": ["2.4"]
    },
    {
      "id": 3,
      "tasks": ["2.5"]
    },
    {
      "id": 4,
      "tasks": ["2.6"]
    },
    {
      "id": 5,
      "tasks": ["4.1", "4.2", "4.3", "4.4"]
    },
    {
      "id": 6,
      "tasks": ["4.5"]
    }
  ]
}
```
