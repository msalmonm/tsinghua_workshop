#!/usr/bin/env python3
"""
RAG Health & Fitness POC - Query Script
Takes a user prompt, searches Elasticsearch, and generates response using Hugging Face
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
HUGGINGFACE_API_KEY = os.getenv('HUGGINGFACE_API_KEY')

if not all([ELASTICSEARCH_URL, ELASTICSEARCH_API_KEY]):
    print("Error: ELASTICSEARCH_URL and ELASTICSEARCH_API_KEY must be set in .env file")
    sys.exit(1)

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

def call_huggingface(prompt):
    """Call Hugging Face Inference API and return response"""
    print("Generating response with Hugging Face...")
    
    # Lista de modelos alternativos para probar
    models_to_try = [
        ("meta-llama/Llama-3.2-3B-Instruct", "Llama 3.2 3B"),
        ("microsoft/Phi-3-mini-4k-instruct", "Phi-3 Mini"),
        ("google/flan-t5-large", "FLAN-T5 Large"),
        ("mistralai/Mistral-7B-Instruct-v0.2", "Mistral-7B")
    ]
    
    headers = {}
    if HUGGINGFACE_API_KEY:
        headers["Authorization"] = f"Bearer {HUGGINGFACE_API_KEY}"
        print(f"Using API key: {HUGGINGFACE_API_KEY[:10]}...")
    else:
        print("Warning: No API key found. Using unauthenticated requests (rate limited)")
    
    # Configurar proxy si está definido en variables de entorno
    proxies = {}
    if os.getenv('HTTP_PROXY'):
        proxies['http'] = os.getenv('HTTP_PROXY')
    if os.getenv('HTTPS_PROXY'):
        proxies['https'] = os.getenv('HTTPS_PROXY')
    
    if proxies:
        print(f"Using proxy configuration: {proxies}")
    
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 500,
            "temperature": 0.7,
            "top_p": 0.95,
            "do_sample": True
        }
    }
    
    # Intentar con cada modelo
    for model_id, model_name in models_to_try:
        try:
            API_URL = f"https://api-inference.huggingface.co/models/{model_id}"
            print(f"\nTrying {model_name}...")
            print(f"API URL: {API_URL}")
            
            response = requests.post(API_URL, headers=headers, json=payload, timeout=60, proxies=proxies if proxies else None)
            # Intentar primero con verificación SSL normal
            try:
                response = requests.post(API_URL, headers=headers, json=payload, timeout=60, proxies=proxies if proxies else None)
            except requests.exceptions.SSLError:
                print(f"SSL error, retrying without verification...")
                response = requests.post(API_URL, headers=headers, json=payload, timeout=60, proxies=proxies if proxies else None, verify=False)
            
            print(f"Response status code: {response.status_code}")
            
            if response.status_code == 503:
                print(f"{model_name} is loading, waiting 20 seconds...")
                import time
                time.sleep(20)
                response = requests.post(API_URL, headers=headers, json=payload, timeout=60, proxies=proxies if proxies else None)
                print(f"Retry response status code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✓ API call successful with {model_name}!")
                
                if isinstance(result, list) and len(result) > 0:
                    return result[0].get('generated_text', '').replace(prompt, '').strip()
                elif isinstance(result, dict):
                    return result.get('generated_text', '').replace(prompt, '').strip()
                else:
                    return str(result)
            else:
                print(f"✗ {model_name} returned error {response.status_code}: {response.text[:200]}")
                continue  # Try next model
                
        except requests.exceptions.ConnectionError as e:
            print(f"✗ Connection error with {model_name}: {str(e)[:100]}")
            continue  # Try next model
        except requests.exceptions.Timeout as e:
            print(f"✗ Timeout with {model_name}: {str(e)[:100]}")
            continue  # Try next model
        except Exception as e:
            print(f"✗ Error with {model_name}: {type(e).__name__}: {str(e)[:100]}")
            continue  # Try next model
    
    # Si todos los modelos fallaron
    print("\n✗ All Hugging Face models failed. Using local response generation...")
    return generate_local_response_with_context(prompt)

def generate_local_response_with_context(prompt):
    """Generate a response using the context from the prompt"""
    # Extract exercises and recipes from the prompt
    lines = prompt.split('\n')
    exercises = []
    recipes = []
    
    in_exercises = False
    in_recipes = False
    
    for line in lines:
        if 'AVAILABLE EXERCISES:' in line:
            in_exercises = True
            in_recipes = False
            continue
        elif 'AVAILABLE RECIPES:' in line:
            in_exercises = False
            in_recipes = True
            continue
        elif 'IMPORTANT:' in line:
            break
            
        if in_exercises and line.strip() and line[0].isdigit():
            exercises.append(line.strip())
        elif in_recipes and line.strip() and line[0].isdigit():
            recipes.append(line.strip())
    
    # Generate response
    response = "Based on your fitness goals and the available resources, here's a personalized plan:\n\n"
    
    if exercises:
        response += "**RECOMMENDED EXERCISES:**\n\n"
        for exercise in exercises[:3]:
            response += f"• {exercise}\n"
        response += "\n**Training Tips:**\n"
        response += "- Perform 3 sets of 8-12 repetitions for each exercise\n"
        response += "- Rest 60-90 seconds between sets\n"
        response += "- Focus on proper form over heavy weight\n"
        response += "- Train 3-4 times per week with rest days in between\n\n"
    
    if recipes:
        response += "**RECOMMENDED NUTRITION:**\n\n"
        for recipe in recipes[:3]:
            response += f"• {recipe}\n"
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
    
    # Call Hugging Face
    response = call_huggingface(prompt)
    
    # Print response
    print("\n" + "=" * 60)
    print("RESPONSE:")
    print("=" * 60)
    print(response)
    print("=" * 60)

if __name__ == "__main__":
    main()
