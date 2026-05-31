#!/usr/bin/env python3
"""
RAG Health & Fitness POC - Data Crawler
Fetches exercises (Static JSON Dump) and recipes (TheMealDB API), 
generates embeddings, and bulk-indexes into Elasticsearch.
"""

import os
import sys
import re
import requests
from dotenv import load_dotenv
from elasticsearch import Elasticsearch, helpers
from sentence_transformers import SentenceTransformer

# Load environment variables
load_dotenv()

# Set OpenMP environment variable to avoid duplicate library warning
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

ELASTICSEARCH_URL = os.getenv('ELASTICSEARCH_URL')
ELASTICSEARCH_API_KEY = os.getenv('ELASTICSEARCH_API_KEY')

if not ELASTICSEARCH_URL or not ELASTICSEARCH_API_KEY:
    print("Error: ELASTICSEARCH_URL and ELASTICSEARCH_API_KEY must be set in .env file")
    sys.exit(1)

# Initialize embedding model
print("Loading embedding model...")
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
print("Model loaded successfully")

def generate_embedding(text):
    """Generate 384-dimensional embedding for text"""
    try:
        return model.encode(text).tolist()
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None

def fetch_exercises():
    """Fetch exercise data from a highly reliable public GitHub JSON dataset"""
    print("\nFetching exercises from public Open Source database...")
    exercises = []
    
    try:
        # Usamos un dump JSON estático y público. Cero fallos, cero bloqueos.
        url = "https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/dist/exercises.json"
        
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        # El dataset tiene más de 800 ejercicios. 
        # Tomaremos los primeros 120 para mantener el MVP rápido de indexar.
        for i, item in enumerate(data[:120]):
            name = item.get('name', 'Unknown Exercise')
            category = item.get('category', 'general')
            level = item.get('level', 'beginner')
            equipment = item.get('equipment', 'body only')
            
            # Los músculos vienen en una lista
            muscles_list = item.get('primaryMuscles', [])
            muscles = ", ".join(muscles_list) if muscles_list else "various muscles"
            
            # Las instrucciones vienen en una lista de pasos
            instructions_list = item.get('instructions', [])
            description = " ".join(instructions_list) if instructions_list else ""
            
            if name and description:
                # Un contexto semántico extremadamente rico para el motor RAG
                search_context = f"{name}. Level: {level}. Equipment: {equipment}. Muscle Group: {muscles}. Category: {category}. Description: {description}"
                
                exercises.append({
                    'id': f"ex_gh_{i}",
                    'name': name,
                    'category': category.capitalize(),
                    'description': description[:800], 
                    'search_context': search_context[:1000]
                })
        
        print(f"Fetched {len(exercises)} exercises from public database")
        return exercises
        
    except Exception as e:
        print(f"Error fetching exercises: {e}")
        return []

def fetch_recipes():
    """Fetch recipe data dynamically using TheMealDB API"""
    print("\nCrawling recipes from TheMealDB...")
    recipes = []
    
    letters_to_fetch = ['a', 'b', 'c', 's'] 
    
    try:
        for letter in letters_to_fetch:
            url = f"https://www.themealdb.com/api/json/v1/1/search.php?f={letter}"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            meals = data.get('meals')
            if not meals:
                continue
                
            for meal in meals:
                name = meal.get('strMeal', '')
                category = meal.get('strCategory', '')
                instructions = meal.get('strInstructions', '').replace('\r\n', ' ')
                
                ingredients = []
                for i in range(1, 21):
                    ingredient = meal.get(f'strIngredient{i}')
                    measure = meal.get(f'strMeasure{i}')
                    if ingredient and ingredient.strip():
                        ingredients.append(f"{measure} {ingredient}".strip())
                
                ingredients_str = ", ".join(ingredients)
                search_context = f"{name}. Category: {category}. Ingredients: {ingredients_str}. Instructions: {instructions}"
                
                recipes.append({
                    'id': f"rec_{meal.get('idMeal')}",
                    'name': name,
                    'category': category,
                    'ingredients': ingredients_str,
                    'instructions': instructions[:800],
                    'search_context': search_context[:1000]
                })
                
        print(f"Fetched {len(recipes)} recipes from API")
        return recipes
    except Exception as e:
        print(f"Error fetching recipes: {e}")
        return []

def create_indices(es_client):
    """Create Elasticsearch indices with proper mappings"""
    print("\nCreating Elasticsearch indices...")
    
    mapping = {
        "mappings": {
            "properties": {
                "name": {"type": "text"},
                "category": {"type": "keyword"},
                "search_context": {"type": "text"},
                "embedding": {
                    "type": "dense_vector",
                    "dims": 384,
                    "index": True,
                    "similarity": "cosine"
                }
            }
        }
    }
    
    for index_name in ["exercises", "recipes"]:
        try:
            if es_client.indices.exists(index=index_name):
                print(f"{index_name.capitalize()} index already exists, deleting...")
                es_client.indices.delete(index=index_name)
            
            es_client.indices.create(index=index_name, body=mapping)
            print(f"Created {index_name} index")
        except Exception as e:
            print(f"Error creating {index_name} index: {e}")
            sys.exit(1)

def bulk_index(es_client, index_name, documents):
    """Bulk index documents efficiently"""
    if not documents:
        print(f"No documents to index for {index_name}.")
        return

    print(f"\nGenerating embeddings and bulk indexing {len(documents)} into {index_name}...")
    
    actions = []
    for doc in documents:
        embedding = generate_embedding(doc.get('search_context', ''))
        
        if embedding:
            doc['embedding'] = embedding
            action = {
                "_index": index_name,
                "_id": doc['id'],
                "_source": doc
            }
            actions.append(action)
    
    if actions:
        try:
            success, _ = helpers.bulk(es_client, actions)
            print(f"Successfully indexed {success} documents into {index_name}")
        except Exception as e:
            print(f"Error during bulk indexing: {e}")

def main():
    print("=" * 60)
    print("RAG Health & Fitness POC - Data Crawler")
    print("=" * 60)
    
    try:
        es_client = Elasticsearch(
            ELASTICSEARCH_URL,
            api_key=ELASTICSEARCH_API_KEY
        )
        es_client.info()
        print("✓ Connected to Elasticsearch")
    except Exception as e:
        print(f"Error connecting to Elasticsearch: {e}")
        sys.exit(1)
    
    # 1. Fetch real data
    exercises = fetch_exercises()
    recipes = fetch_recipes()
    
    # 2. Reset indices
    create_indices(es_client)
    
    # 3. Vectorize and bulk load
    bulk_index(es_client, "exercises", exercises)
    bulk_index(es_client, "recipes", recipes)
    
    print("\n" + "=" * 60)
    print("✓ Crawler completed successfully!")
    print("=" * 60)

if __name__ == "__main__":
    main()