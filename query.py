#!/usr/bin/env python3
"""
RAG Health & Fitness POC - Query Script
Takes a user prompt, searches Elasticsearch, and generates response using Gemini
"""

import os
import sys
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Validate environment variables
ELASTICSEARCH_URL = os.getenv('ELASTICSEARCH_URL')
ELASTICSEARCH_API_KEY = os.getenv('ELASTICSEARCH_API_KEY')
GOOGLE_GEMINI_API_KEY = os.getenv('GOOGLE_GEMINI_API_KEY')

if not all([ELASTICSEARCH_URL, ELASTICSEARCH_API_KEY, GOOGLE_GEMINI_API_KEY]):
    print("Error: ELASTICSEARCH_URL, ELASTICSEARCH_API_KEY, and GOOGLE_GEMINI_API_KEY must be set in .env file")
    sys.exit(1)

# Initialize embedding model
print("Loading embedding model...")
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
print("Model loaded")

# Initialize Gemini
genai.configure(api_key=GOOGLE_GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

def generate_embedding(text):
    """Generate 384-dimensional embedding for query"""
    try:
        embedding = model.encode(text)
        return embedding.tolist()
    except Exception as e:
        print(f"Error generating embedding: {e}")
        sys.exit(1)

def search_elasticsearch(es_client, query_embedding):
    """Search for top 3 exercises and recipes"""
    print("Searching Elasticsearch...")
    
    try:
        # Search exercises
        exercises_query = {
            "knn": {
                "field": "embedding",
                "query_vector": query_embedding,
                "k": 3,
                "num_candidates": 50
            },
            "_source": ["name", "description"]
        }
        exercises_response = es_client.search(index="exercises", body=exercises_query)
        exercises = [hit['_source'] for hit in exercises_response['hits']['hits']]
        
        # Search recipes
        recipes_query = {
            "knn": {
                "field": "embedding",
                "query_vector": query_embedding,
                "k": 3,
                "num_candidates": 50
            },
            "_source": ["name", "ingredients"]
        }
        recipes_response = es_client.search(index="recipes", body=recipes_query)
        recipes = [hit['_source'] for hit in recipes_response['hits']['hits']]
        
        print(f"Found {len(exercises)} exercises and {len(recipes)} recipes")
        return exercises, recipes
    
    except Exception as e:
        print(f"Error searching Elasticsearch: {e}")
        sys.exit(1)

def build_prompt(user_query, exercises, recipes):
    """Construct RAG prompt with retrieved context"""
    prompt = f"""You are a fitness and nutrition expert. A user has asked: "{user_query}"

Based on the following exercises and recipes, provide a helpful, personalized response.

AVAILABLE EXERCISES:
"""
    
    for i, ex in enumerate(exercises, 1):
        prompt += f"{i}. {ex['name']}: {ex['description']}\n"
    
    prompt += "\nAVAILABLE RECIPES:\n"
    
    for i, recipe in enumerate(recipes, 1):
        prompt += f"{i}. {recipe['name']}: {recipe['ingredients']}\n"
    
    prompt += """
IMPORTANT: Only recommend exercises and recipes from the lists above. Do not invent new ones.
Provide a practical, actionable response that addresses the user's goal."""
    
    return prompt

def call_gemini(prompt):
    """Call Gemini API and return response"""
    print("Generating response with Gemini...")
    
    try:
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        sys.exit(1)

def main():
    """Main execution"""
    if len(sys.argv) < 2:
        print("Usage: python query.py \"your fitness question\"")
        print("Example: python query.py \"I want to build muscle and lose fat\"")
        sys.exit(1)
    
    user_query = " ".join(sys.argv[1:])
    
    print("=" * 60)
    print("RAG Health & Fitness POC - Query")
    print("=" * 60)
    print(f"Query: {user_query}\n")
    
    # Initialize Elasticsearch client
    try:
        es_client = Elasticsearch(
            ELASTICSEARCH_URL,
            api_key=ELASTICSEARCH_API_KEY
        )
        es_client.info()
    except Exception as e:
        print(f"Error connecting to Elasticsearch: {e}")
        sys.exit(1)
    
    # Generate query embedding
    query_embedding = generate_embedding(user_query)
    
    # Search Elasticsearch
    exercises, recipes = search_elasticsearch(es_client, query_embedding)
    
    # Build prompt
    prompt = build_prompt(user_query, exercises, recipes)
    
    # Call Gemini
    response = call_gemini(prompt)
    
    # Print response
    print("\n" + "=" * 60)
    print("RESPONSE:")
    print("=" * 60)
    print(response)
    print("=" * 60)

if __name__ == "__main__":
    main()
