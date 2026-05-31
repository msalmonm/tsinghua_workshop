#!/usr/bin/env python3
"""
RAG Health & Fitness API - FastAPI Backend
Exposes query.py functionality as REST API for Next.js frontend
"""

import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer
from openai import OpenAI

# Load environment variables
load_dotenv()

# Set OpenMP environment variable
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

# Initialize clients
es_client = Elasticsearch(
    os.getenv('ELASTICSEARCH_URL'),
    api_key=os.getenv('ELASTICSEARCH_API_KEY')
)

openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Load embedding model
print("Loading embedding model...")
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
print("Model loaded successfully.")

# Initialize FastAPI app
app = FastAPI(title="Fitness RAG API", version="1.0.0")

# CORS configuration (critical for Next.js frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production: ["https://your-app.vercel.app"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response models
class UserProfile(BaseModel):
    age: int
    sex: str
    weight_kg: float
    height_cm: float

class QueryRequest(BaseModel):
    query: str
    user_profile: UserProfile

class RecommendationResponse(BaseModel):
    response: str
    raw_data: dict

def search_elasticsearch(index_name: str, query_vector: list, k: int = 3):
    """Perform k-NN search in Elasticsearch"""
    search_query = {
        "knn": {
            "field": "embedding",
            "query_vector": query_vector,
            "k": k,
            "num_candidates": 50
        },
        "_source": ["name", "search_context", "category", "description", "ingredients"]
    }
    
    try:
        response = es_client.search(index=index_name, body=search_query)
        results = []
        for hit in response["hits"]["hits"]:
            results.append(hit["_source"])
        return results
    except Exception as e:
        print(f"Error searching {index_name}: {e}")
        return []

@app.get("/health")
def health_check():
    """Health check endpoint for deployment monitoring"""
    return {
        "status": "active",
        "message": "RAG API is running",
        "elasticsearch": "connected" if es_client.ping() else "disconnected"
    }

@app.post("/api/recommend", response_model=RecommendationResponse)
def get_recommendation(request: QueryRequest):
    """Main RAG pipeline endpoint"""
    
    # 1. Generate query embedding
    try:
        query_vector = model.encode(request.query).tolist()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating embedding: {str(e)}")
    
    # 2. Retrieve context from Elasticsearch
    exercises = search_elasticsearch("exercises", query_vector, k=3)
    recipes = search_elasticsearch("recipes", query_vector, k=3)
    
    # Prepare context for LLM
    context_text = "RETRIEVED EXERCISES:\n"
    for ex in exercises:
        context_text += f"- {ex.get('search_context', '')}\n"
    
    context_text += "\nRETRIEVED RECIPES:\n"
    for rec in recipes:
        context_text += f"- {rec.get('search_context', '')}\n"
    
    # 3. Generate response with OpenAI
    system_prompt = """You are an expert fitness trainer and nutritionist. Your goal is to create a personalized plan based ONLY on the exercises and recipes provided in the context.

Use a motivating and clear tone. Format your response with Markdown (use bold and lists).

IMPORTANT RULES:
1. Only recommend exercises and recipes from the provided context
2. Provide specific, actionable advice
3. Consider the user's profile (age, sex, weight, height)
4. Structure your response clearly
5. Be encouraging and supportive"""

    user_prompt = f"""User Profile: {request.user_profile.age} years old, {request.user_profile.sex}, {request.user_profile.weight_kg}kg, {request.user_profile.height_cm}cm.

Goal: {request.query}

DATABASE CONTEXT:
{context_text}

Please generate a personalized recommendation using this context."""

    try:
        chat_completion = openai_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="gpt-4o-mini",
            temperature=0.7,
            max_tokens=800
        )
        
        final_response = chat_completion.choices[0].message.content
        
        # Return both natural language response and raw data for UI
        return {
            "response": final_response,
            "raw_data": {
                "exercises": exercises,
                "recipes": recipes
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI error: {str(e)}")

@app.get("/")
def root():
    """Root endpoint with API info"""
    return {
        "name": "Fitness RAG API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "recommend": "/api/recommend (POST)",
            "docs": "/docs"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
