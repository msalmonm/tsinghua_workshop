# Requirements Document

## Introduction

The RAG Health & Fitness Engine is a **simple proof-of-concept (POC)** for a school project that demonstrates Retrieval-Augmented Generation (RAG). The system consists of:
1. A Python crawler that indexes exercise/recipe data into Elasticsearch
2. A simple Python script that takes a user prompt, searches Elasticsearch, and generates a response using Google Gemini

**Scope**: This is a minimal viable product (MVP) for educational purposes, not a production system.

## Glossary

- **System**: The RAG POC consisting of crawler and query scripts
- **User**: Person running the Python scripts from command line
- **Vector_Store**: Elasticsearch Cloud instance storing exercise and recipe embeddings
- **Embedding_Model**: sentence-transformers/all-MiniLM-L6-v2 model (Python)
- **LLM**: Google Gemini 1.5 Flash language model
- **Crawler**: Python script that fetches, embeds, and indexes data
- **Query_Script**: Python script that takes a prompt, searches, and generates response
- **Exercise_Doc**: Exercise document with name, description, and embedding
- **Recipe_Doc**: Recipe document with name, ingredients, and embedding

## Requirements

### Requirement 1: Data Crawler Implementation

**User Story:** As a Developer, I want a Python script that crawls and indexes data, so that I can populate Elasticsearch with searchable content.

#### Acceptance Criteria

1. THE Crawler SHALL fetch at least 50 exercise documents from a public API or dataset
2. THE Crawler SHALL fetch at least 50 recipe documents from a public source
3. THE Crawler SHALL generate 384-dimensional embeddings using sentence-transformers
4. THE Crawler SHALL create Elasticsearch indices if they don't exist
5. THE Crawler SHALL bulk index documents with embeddings into Elasticsearch
6. THE Crawler SHALL print progress to console

### Requirement 2: Elasticsearch Index Setup

**User Story:** As a Developer, I want properly configured indices, so that vector search works correctly.

#### Acceptance Criteria

1. THE exercises index SHALL have fields: name, description, embedding (384-dim dense_vector)
2. THE recipes index SHALL have fields: name, ingredients, embedding (384-dim dense_vector)
3. THE dense_vector fields SHALL use cosine similarity
4. THE indices SHALL support k-NN search

### Requirement 3: Query Script Implementation

**User Story:** As a User, I want a Python script that answers my fitness questions, so that I can get personalized recommendations.

#### Acceptance Criteria

1. THE Query_Script SHALL accept a text prompt as command-line argument
2. THE Query_Script SHALL generate an embedding for the prompt
3. THE Query_Script SHALL search Elasticsearch for top 3 relevant exercises and recipes
4. THE Query_Script SHALL construct a prompt with retrieved context
5. THE Query_Script SHALL call Google Gemini API to generate a response
6. THE Query_Script SHALL print the response to console

### Requirement 4: Environment Configuration

**User Story:** As a Developer, I want to configure API credentials, so that the scripts can access external services.

#### Acceptance Criteria

1. THE System SHALL read ELASTICSEARCH_URL from environment variables
2. THE System SHALL read ELASTICSEARCH_API_KEY from environment variables
3. THE System SHALL read GOOGLE_GEMINI_API_KEY from environment variables
4. THE System SHALL fail with clear error if credentials are missing

### Requirement 5: Basic Error Handling

**User Story:** As a User, I want clear error messages, so that I understand what went wrong.

#### Acceptance Criteria

1. WHEN Elasticsearch is unreachable, THE System SHALL print an error message
2. WHEN Gemini API fails, THE System SHALL print an error message
3. WHEN embedding generation fails, THE System SHALL print an error message
4. THE error messages SHALL NOT expose API keys
