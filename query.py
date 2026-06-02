#!/usr/bin/env python3
"""
RAG Health & Fitness POC - Query Script
Takes a user prompt, searches Elasticsearch, and generates response using OpenAI API
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
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

if not all([ELASTICSEARCH_URL, ELASTICSEARCH_API_KEY]):
    print("Error: ELASTICSEARCH_URL and ELASTICSEARCH_API_KEY must be set in .env file")
    sys.exit(1)

if not OPENAI_API_KEY:
    print("Warning: OPENAI_API_KEY not set. Will use fallback response generation.")
    print("Get your API key at: https://platform.openai.com/api-keys\n")

# Initialize embedding model
print("Loading embedding model...")
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
print("Model loaded")

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
        # Search exercises - get search_context which contains full JSON
        exercises_query = {
            "knn": {
                "field": "embedding",
                "query_vector": query_embedding,
                "k": 3,
                "num_candidates": 50
            },
            "_source": ["search_context"]
        }
        exercises_response = es_client.search(index="exercises", body=exercises_query)
        exercises = []
        for hit in exercises_response['hits']['hits']:
            import json
            # Parse JSON string from search_context
            try:
                exercise_data = json.loads(hit['_source']['search_context'])
                exercises.append(exercise_data)
            except:
                exercises.append(hit['_source'])
        
        # Search recipes - get search_context which contains full JSON
        recipes_query = {
            "knn": {
                "field": "embedding",
                "query_vector": query_embedding,
                "k": 3,
                "num_candidates": 50
            },
            "_source": ["search_context"]
        }
        recipes_response = es_client.search(index="recipes", body=recipes_query)
        recipes = []
        for hit in recipes_response['hits']['hits']:
            import json
            # Parse JSON string from search_context
            try:
                recipe_data = json.loads(hit['_source']['search_context'])
                recipes.append(recipe_data)
            except:
                recipes.append(hit['_source'])
        
        print(f"Found {len(exercises)} exercises and {len(recipes)} recipes")
        return exercises, recipes
    
    except Exception as e:
        print(f"Error searching Elasticsearch: {e}")
        sys.exit(1)

def call_openai(user_query, exercises, recipes):
    """Call OpenAI Chat Completions API"""
    print("Generating response with OpenAI...")
    
    if not OPENAI_API_KEY:
        print("No OpenAI API key found. Using fallback response...")
        return generate_fallback_response(exercises, recipes)
    
    # Prepare context strings with new schema
    exercises_str = ""
    for ex in exercises:
        exercises_str += f"- {ex.get('name', 'Unknown')}: "
        exercises_str += f"{ex.get('instructions', ex.get('description', 'No details'))} "
        exercises_str += f"(Target: {ex.get('target_muscle', 'N/A')}, "
        exercises_str += f"Equipment: {ex.get('equipment', 'N/A')}, "
        exercises_str += f"Intensity MET: {ex.get('estimated_met', 'N/A')})\n"
    
    recipes_str = ""
    for r in recipes:
        recipes_str += f"- {r.get('name', 'Unknown')}: "
        recipes_str += f"{r.get('ingredients', 'No ingredients listed')} "
        if 'macros' in r:
            m = r['macros']
            recipes_str += f"(Calories: {m.get('calories', 0)}, "
            recipes_str += f"Protein: {m.get('protein_g', 0)}g, "
            recipes_str += f"Carbs: {m.get('carbs_g', 0)}g, "
            recipes_str += f"Fats: {m.get('fats_g', 0)}g) "
        if 'diets' in r and r['diets']:
            recipes_str += f"[{', '.join(r['diets'])}] "
        if 'ready_in_minutes' in r:
            recipes_str += f"Ready in: {r['ready_in_minutes']} min"
        recipes_str += "\n"
    
    # Build messages for Chat Completions API
    messages = [
        {
            "role": "system",
            "content": """You are an expert fitness and nutrition coach. Your role is to provide personalized, 
actionable advice based on the user's goals and the available exercises and recipes provided to you.

IMPORTANT RULES:
1. Only recommend exercises and recipes from the provided lists
2. Do not invent or suggest exercises/recipes not in the context
3. Provide practical, specific advice with clear action steps
4. Structure your response with clear sections for exercises and nutrition
5. Include helpful tips for training and nutrition
6. Be encouraging and supportive"""
        },
        {
            "role": "user",
            "content": f"""User Goal: {user_query}

AVAILABLE EXERCISES:
{exercises_str}

AVAILABLE RECIPES:
{recipes_str}

Please provide a personalized fitness and nutrition plan based on the user's goal and the available resources above."""
        }
    ]
    
    # Try with gpt-4o-mini first (faster and cheaper), then gpt-3.5-turbo
    models_to_try = ["gpt-4o-mini", "gpt-3.5-turbo"]
    
    for model in models_to_try:
        try:
            print(f"Trying OpenAI model: {model}...")
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 800
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                print(f"✓ Successfully generated response with {model}")
                return content.strip()
            
            elif response.status_code == 404 and model == "gpt-4o-mini":
                print(f"✗ Model {model} not available, trying next...")
                continue
            
            else:
                error_data = response.json()
                error_msg = error_data.get('error', {}).get('message', 'Unknown error')
                print(f"✗ OpenAI API error ({response.status_code}): {error_msg}")
                
                if response.status_code == 401:
                    print("Invalid API key. Please check your OPENAI_API_KEY in .env file")
                    break
                elif response.status_code == 429:
                    print("Rate limit exceeded. Please wait or upgrade your OpenAI plan")
                    break
                else:
                    continue  # Try next model
        
        except requests.exceptions.ConnectionError as e:
            print(f"✗ Connection error: {str(e)[:100]}")
            continue
        except requests.exceptions.Timeout:
            print(f"✗ Request timeout with {model}")
            continue
        except Exception as e:
            print(f"✗ Error with {model}: {type(e).__name__}: {str(e)[:100]}")
            continue
    
    # All models failed, use fallback
    print("\n✗ All OpenAI models failed. Using fallback response...")
    return generate_fallback_response(exercises, recipes)

def generate_fallback_response(exercises, recipes):
    """Generate a structured response using the retrieved context"""
    response = "Based on your fitness goals and the available resources, here's a personalized plan:\n\n"
    
    if exercises:
        response += "**RECOMMENDED EXERCISES:**\n\n"
        for i, ex in enumerate(exercises, 1):
            response += f"{i}. {ex.get('name', 'Unknown')}: "
            response += f"{ex.get('instructions', ex.get('description', 'No details available'))}\n"
            response += f"   - Target Muscle: {ex.get('target_muscle', 'N/A')}\n"
            response += f"   - Equipment: {ex.get('equipment', 'N/A')}\n"
            response += f"   - Intensity (MET): {ex.get('estimated_met', 'N/A')}\n"
        response += "\n**Training Tips:**\n"
        response += "- Perform 3 sets of 8-12 repetitions for each exercise\n"
        response += "- Rest 60-90 seconds between sets\n"
        response += "- Focus on proper form over heavy weight\n"
        response += "- Train 3-4 times per week with rest days in between\n\n"
    
    if recipes:
        response += "**RECOMMENDED NUTRITION:**\n\n"
        for i, recipe in enumerate(recipes, 1):
            response += f"{i}. {recipe.get('name', 'Unknown')}\n"
            response += f"   - Ingredients: {recipe.get('ingredients', 'Not listed')}\n"
            if 'macros' in recipe:
                m = recipe['macros']
                response += f"   - Macros: {m.get('calories', 0)} cal | "
                response += f"{m.get('protein_g', 0)}g protein | "
                response += f"{m.get('carbs_g', 0)}g carbs | "
                response += f"{m.get('fats_g', 0)}g fats\n"
            if 'diets' in recipe and recipe['diets']:
                response += f"   - Diet Tags: {', '.join(recipe['diets'])}\n"
            if 'ready_in_minutes' in recipe:
                response += f"   - Prep Time: {recipe['ready_in_minutes']} minutes\n"
        response += "\n**Nutrition Tips:**\n"
        response += "- Aim for 0.7-1g of protein per pound of body weight daily\n"
        response += "- Eat protein-rich meals within 2 hours post-workout\n"
        response += "- Stay hydrated (8-10 glasses of water per day)\n"
        response += "- Get 7-9 hours of quality sleep for recovery\n\n"
    
    response += "**KEY TO SUCCESS:**\n"
    response += "Consistency is crucial! Stick to your training and nutrition plan for at least 8-12 weeks to see significant results.\n"
    
    return response

def main():
    """Main execution"""
    if len(sys.argv) < 2:
        print("Usage: python query.py \"your fitness question\"")
        print("Example: python query.py \"I want to build muscle and lose fat\"")
        sys.exit(1)
    
    user_query = " ".join(sys.argv[1:])
    
    print("=" * 60)
    print("RAG Health & Fitness POC - Query (OpenAI)")
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
    
    # Call OpenAI
    response = call_openai(user_query, exercises, recipes)
    
    # Print response
    print("\n" + "=" * 60)
    print("RESPONSE:")
    print("=" * 60)
    print(response)
    print("=" * 60)

if __name__ == "__main__":
    main()
