#!/usr/bin/env python3
"""
RAG Health & Fitness POC - Data Crawler
Fetches exercises and recipes, generates embeddings, and indexes into Elasticsearch
"""

import os
import sys
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer
import requests

# Load environment variables
load_dotenv()

# Set OpenMP environment variable to avoid duplicate library warning
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

# Validate environment variables
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
        embedding = model.encode(text)
        return embedding.tolist()
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None

def fetch_exercises():
    """Fetch exercise data from Wger API"""
    print("\nFetching exercises from Wger API...")
    exercises = []
    
    try:
        # Wger Workout Manager API - public exercises
        url = "https://wger.de/api/v2/exercise/?language=2&limit=50"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        for item in data.get('results', []):
            name = item.get('name', 'Unknown Exercise')
            description = item.get('description', '')
            # Clean HTML tags from description
            import re
            description = re.sub('<[^<]+?>', '', description)
            
            if name and description:
                exercises.append({
                    'name': name,
                    'description': description[:500]  # Limit length
                })
        
        print(f"Fetched {len(exercises)} exercises from API")
        
        # If API returned no exercises, use fallback
        if len(exercises) == 0:
            print("API returned no exercises, using fallback sample exercises...")
            exercises = [
                {'name': 'Push-ups', 'description': 'Upper body exercise targeting chest, shoulders, and triceps'},
                {'name': 'Squats', 'description': 'Lower body exercise targeting quads, hamstrings, and glutes'},
                {'name': 'Plank', 'description': 'Core stability exercise engaging abs and back muscles'},
                {'name': 'Lunges', 'description': 'Single-leg exercise for lower body strength and balance'},
                {'name': 'Pull-ups', 'description': 'Upper body pulling exercise for back and biceps'},
                {'name': 'Burpees', 'description': 'Full body cardio exercise combining squat, plank, and jump'},
                {'name': 'Deadlifts', 'description': 'Compound exercise for posterior chain, targeting back, glutes, and hamstrings'},
                {'name': 'Bench Press', 'description': 'Upper body pressing exercise for chest, shoulders, and triceps'},
            ]
        
        return exercises
    
    except Exception as e:
        print(f"Error fetching exercises: {e}")
        # Fallback: create sample exercises
        print("Using fallback sample exercises...")
        return [
            {'name': 'Push-ups', 'description': 'Upper body exercise targeting chest, shoulders, and triceps'},
            {'name': 'Squats', 'description': 'Lower body exercise targeting quads, hamstrings, and glutes'},
            {'name': 'Plank', 'description': 'Core stability exercise engaging abs and back muscles'},
            {'name': 'Lunges', 'description': 'Single-leg exercise for lower body strength and balance'},
            {'name': 'Pull-ups', 'description': 'Upper body pulling exercise for back and biceps'},
            {'name': 'Burpees', 'description': 'Full body cardio exercise combining squat, plank, and jump'},
            {'name': 'Deadlifts', 'description': 'Compound exercise for posterior chain, targeting back, glutes, and hamstrings'},
            {'name': 'Bench Press', 'description': 'Upper body pressing exercise for chest, shoulders, and triceps'},
        ]

def fetch_recipes():
    """Fetch recipe data from sample dataset"""
    print("\nFetching recipes...")
    
    # Sample recipes (in production, would scrape from API or website)
    recipes = [
        {'name': 'Protein Smoothie', 'ingredients': 'banana, protein powder, almond milk, peanut butter, ice'},
        {'name': 'Grilled Chicken Salad', 'ingredients': 'chicken breast, mixed greens, tomatoes, cucumber, olive oil, lemon'},
        {'name': 'Oatmeal with Berries', 'ingredients': 'oats, blueberries, strawberries, honey, almonds'},
        {'name': 'Tuna Wrap', 'ingredients': 'whole wheat tortilla, tuna, lettuce, tomato, avocado'},
        {'name': 'Greek Yogurt Bowl', 'ingredients': 'greek yogurt, granola, banana, honey, chia seeds'},
        {'name': 'Egg White Omelet', 'ingredients': 'egg whites, spinach, mushrooms, bell peppers, cheese'},
        {'name': 'Quinoa Bowl', 'ingredients': 'quinoa, black beans, corn, avocado, lime, cilantro'},
        {'name': 'Salmon with Vegetables', 'ingredients': 'salmon fillet, broccoli, carrots, olive oil, garlic'},
        {'name': 'Protein Pancakes', 'ingredients': 'oats, banana, eggs, protein powder, cinnamon'},
        {'name': 'Chicken Stir Fry', 'ingredients': 'chicken, broccoli, bell peppers, soy sauce, ginger, rice'},
    ]
    
    print(f"Fetched {len(recipes)} recipes")
    return recipes

def create_indices(es_client):
    """Create Elasticsearch indices with proper mappings"""
    print("\nCreating Elasticsearch indices...")
    
    # Exercises index mapping
    exercises_mapping = {
        "mappings": {
            "properties": {
                "name": {"type": "text"},
                "description": {"type": "text"},
                "embedding": {
                    "type": "dense_vector",
                    "dims": 384,
                    "index": True,
                    "similarity": "cosine"
                }
            }
        }
    }
    
    # Recipes index mapping
    recipes_mapping = {
        "mappings": {
            "properties": {
                "name": {"type": "text"},
                "ingredients": {"type": "text"},
                "embedding": {
                    "type": "dense_vector",
                    "dims": 384,
                    "index": True,
                    "similarity": "cosine"
                }
            }
        }
    }
    
    try:
        # Create exercises index
        if es_client.indices.exists(index="exercises"):
            print("Exercises index already exists, deleting...")
            es_client.indices.delete(index="exercises")
        es_client.indices.create(index="exercises", body=exercises_mapping)
        print("Created exercises index")
        
        # Create recipes index
        if es_client.indices.exists(index="recipes"):
            print("Recipes index already exists, deleting...")
            es_client.indices.delete(index="recipes")
        es_client.indices.create(index="recipes", body=recipes_mapping)
        print("Created recipes index")
        
    except Exception as e:
        print(f"Error creating indices: {e}")
        sys.exit(1)

def bulk_index(es_client, index_name, documents, text_field):
    """Bulk index documents with embeddings"""
    print(f"\nIndexing {len(documents)} documents into {index_name}...")
    
    for i, doc in enumerate(documents):
        try:
            # Generate embedding
            text = doc.get(text_field, '')
            embedding = generate_embedding(text)
            
            if embedding:
                doc['embedding'] = embedding
                es_client.index(index=index_name, document=doc)
                
                if (i + 1) % 10 == 0:
                    print(f"Indexed {i + 1}/{len(documents)} documents")
        
        except Exception as e:
            print(f"Error indexing document {i}: {e}")
            continue
    
    print(f"Successfully indexed {len(documents)} documents into {index_name}")

def main():
    """Main execution"""
    print("=" * 60)
    print("RAG Health & Fitness POC - Data Crawler")
    print("=" * 60)
    
    # Initialize Elasticsearch client
    try:
        es_client = Elasticsearch(
            ELASTICSEARCH_URL,
            api_key=ELASTICSEARCH_API_KEY
        )
        # Test connection
        es_client.info()
        print("✓ Connected to Elasticsearch")
    except Exception as e:
        print(f"Error connecting to Elasticsearch: {e}")
        sys.exit(1)
    
    # Fetch data
    exercises = fetch_exercises()
    recipes = fetch_recipes()
    
    # Create indices
    create_indices(es_client)
    
    # Index data
    bulk_index(es_client, "exercises", exercises, "description")
    bulk_index(es_client, "recipes", recipes, "ingredients")
    
    print("\n" + "=" * 60)
    print("✓ Crawler completed successfully!")
    print(f"  - Indexed {len(exercises)} exercises")
    print(f"  - Indexed {len(recipes)} recipes")
    print("=" * 60)

if __name__ == "__main__":
    main()
