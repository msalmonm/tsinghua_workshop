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
    response: str  # JSON string (for backward compatibility)
    plan: dict     # Parsed JSON plan
    raw_data: dict # Raw retrieved exercises and recipes

def search_elasticsearch(index_name: str, query_vector: list, k: int = 3, boost_fatsecret: bool = False):
    """
    Perform k-NN search in Elasticsearch with optional FatSecret prioritization.
    
    Args:
        index_name: Index to search (exercises or recipes)
        query_vector: Query embedding vector
        k: Number of results to retrieve
        boost_fatsecret: If True, prioritize FatSecret recipes (IDs starting with 'rec_fs_')
    """
    search_query = {
        "knn": {
            "field": "embedding",
            "query_vector": query_vector,
            "k": k * 3 if boost_fatsecret else k,  # Retrieve more for filtering
            "num_candidates": 100 if boost_fatsecret else 50
        },
        "_source": ["search_context"]
    }
    
    try:
        response = es_client.search(index=index_name, body=search_query)
        results = []
        
        for hit in response["hits"]["hits"]:
            # Parse JSON string from search_context to get full structured data
            import json
            try:
                parsed_data = json.loads(hit["_source"]["search_context"])
                parsed_data["_score"] = hit["_score"]  # Preserve relevance score
                results.append(parsed_data)
            except:
                # Fallback if search_context is not valid JSON
                fallback_data = hit["_source"]
                fallback_data["_score"] = hit["_score"]
                results.append(fallback_data)
        
        # Prioritize FatSecret recipes if requested
        if boost_fatsecret and index_name == "recipes":
            fatsecret_recipes = [r for r in results if r.get("id", "").startswith("rec_fs_")]
            other_recipes = [r for r in results if not r.get("id", "").startswith("rec_fs_")]
            
            # Return FatSecret first, then others, up to k total
            results = (fatsecret_recipes + other_recipes)[:k]
        else:
            results = results[:k]
        
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
    
    # 2. Retrieve context from Elasticsearch (prioritize FatSecret for recipes)
    exercises = search_elasticsearch("exercises", query_vector, k=10)
    recipes = search_elasticsearch("recipes", query_vector, k=15, boost_fatsecret=True)
    
    # Prepare comprehensive context with all retrieved data
    import json
    context_json = {
        "exercises": exercises,
        "recipes": recipes
    }
    context_text = json.dumps(context_json, ensure_ascii=False, indent=2)
    
    # 3. Generate response with OpenAI GPT-4o-mini (structured JSON output)
    system_prompt = """You are a fitness and nutrition planning assistant.

Use ONLY the retrieved exercises and recipes from the DATABASE CONTEXT.
Return ONLY valid JSON.
Do not return Markdown.
Do not invent exercises or recipes.

The frontend will use this JSON to render a single-page dashboard with a weekly calendar.

The plan must consider:
- user profile
- user goal
- allergies or restrictions if mentioned
- diet type if mentioned
- number of workout days if mentioned
- available recipes and exercises from the retrieved context

CRITICAL: Always respond in the SAME LANGUAGE as the user's query. 
- If query is in Spanish, return all text fields in Spanish.
- If query is in English, return all text fields in English.
- If query is in Chinese, return all text fields in Chinese.

PRIORITIZATION RULE: Recipes with IDs starting with "rec_fs_" are from FatSecret and contain detailed macro data. 
ALWAYS prioritize these recipes over others (rec_mdb_*) when creating meal plans.

Return exactly this JSON structure:
{
  "plan_summary": {
    "title": "",
    "goal_detected": "",
    "short_summary": "",
    "focus": "",
    "difficulty_level": ""
  },
  "user_profile_summary": {
    "age": 0,
    "sex": "",
    "weight_kg": 0,
    "height_cm": 0,
    "bmi": 0
  },
  "nutrition_summary": {
    "total_daily_calories_avg": 0,
    "total_daily_protein_g_avg": 0,
    "total_daily_carbs_g_avg": 0,
    "total_daily_fats_g_avg": 0,
    "macro_notes": ""
  },
  "macro_bars": [
    {"label": "Calories", "value": 0, "unit": "kcal", "target": 0},
    {"label": "Protein", "value": 0, "unit": "g", "target": 0},
    {"label": "Carbs", "value": 0, "unit": "g", "target": 0},
    {"label": "Fats", "value": 0, "unit": "g", "target": 0}
  ],
  "meal_options": {
    "breakfast": [
      {
        "recipe_id": "",
        "recipe_name": "",
        "description": "",
        "image_url": "",
        "recipe_url": "",
        "rating": null,
        "ready_in_minutes": null,
        "diet_tags": [],
        "calories": 0,
        "protein_g": 0,
        "carbs_g": 0,
        "fats_g": 0,
        "ingredients": "",
        "instructions": "",
        "reason_selected": ""
      }
    ],
    "lunch": [],
    "dinner": []
  },
  "workout_options": [
    {
      "exercise_id": "",
      "name": "",
      "target_muscle": "",
      "secondary_muscles": [],
      "equipment": "",
      "estimated_met": null,
      "sets": 0,
      "reps": "",
      "rest_seconds": 0,
      "instructions": "",
      "reason_selected": ""
    }
  ],
  "weekly_calendar": [
    {
      "day": "Monday",
      "breakfast": "",
      "lunch": "",
      "dinner": "",
      "workout": {
        "focus": "",
        "exercises": []
      },
      "daily_totals": {
        "calories": 0,
        "protein_g": 0,
        "carbs_g": 0,
        "fats_g": 0
      },
      "notes": ""
    }
  ],
  "ai_recommendations": {
    "main_tip": "",
    "personalized_notes": [],
    "nutrition_tips": [],
    "workout_tips": [],
    "safety_notes": []
  },
  "retrieved_data_summary": {
    "recipes_used": [],
    "exercises_used": [],
    "ir_explanation": ""
  }
}

Planning rules:
1. Create exactly 3 breakfast options, 3 lunch options, and 3 dinner options when enough recipes are available.
2. If there are not enough recipes, reuse the best available recipes logically and explain this in the notes.
3. Create a weekly calendar from Monday to Sunday (7 days).
4. Assign meals to each day using the selected meal options.
5. Assign workout routines only on the number of workout days requested by the user.
6. If the user does not specify workout days, default to 3 workout days per week.
7. On non-workout days, set workout focus to "Rest day" and exercises to an empty array.
8. Respect allergies, restrictions, diet type, and preferences mentioned in the user query.
9. Calculate daily totals from the selected breakfast, lunch, and dinner.
10. Macro bars should represent average daily macros across the weekly calendar.
11. Keep recommendations short, useful, and dashboard-friendly.
12. ALWAYS prioritize FatSecret recipes (rec_fs_*) because they have complete macro data.
13. Calculate BMI using the formula: weight_kg / (height_cm/100)^2"""

    user_prompt = f"""User Profile:
- Age: {request.user_profile.age} years old
- Sex: {request.user_profile.sex}
- Weight: {request.user_profile.weight_kg} kg
- Height: {request.user_profile.height_cm} cm

User Goal/Query: {request.query}

DATABASE CONTEXT (Retrieved from Elasticsearch using k-NN semantic search):
{context_text}

Generate a complete weekly fitness and nutrition plan using ONLY the exercises and recipes provided above.
Remember: Respond in the same language as the user's query.
Prioritize recipes with IDs starting with "rec_fs_" (FatSecret) for accurate macro tracking."""

    # Try GPT-5.4-mini first, fallback to GPT-4o-mini if needed
    models_to_try = [
        {"name": "gpt-5.4-mini", "max_param": "max_completion_tokens"},
        {"name": "gpt-4o-mini", "max_param": "max_tokens"}
    ]
    
    final_response = None
    last_error = None
    
    for model_config in models_to_try:
        try:
            params = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "model": model_config["name"],
                "temperature": 0.7,
                model_config["max_param"]: 4000,
                "response_format": {"type": "json_object"}
            }
            
            chat_completion = openai_client.chat.completions.create(**params)
            final_response = chat_completion.choices[0].message.content
            print(f"✓ Successfully used model: {model_config['name']}")
            break
            
        except Exception as e:
            last_error = e
            print(f"✗ Model {model_config['name']} failed: {str(e)}")
            if model_config == models_to_try[-1]:  # Last model
                import traceback
                error_detail = f"All models failed. Last error: {str(e)}"
                print(f"Traceback: {traceback.format_exc()}")
                raise HTTPException(status_code=500, detail=error_detail)
            continue
    
    if not final_response:
        raise HTTPException(status_code=500, detail=f"No model succeeded. Last error: {str(last_error)}")
        
        # Parse JSON response
        import json
        try:
            parsed_json = json.loads(final_response)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="OpenAI returned invalid JSON")
        
        # Return structured JSON plan
        return {
            "response": final_response,  # Complete JSON plan as string (for backward compatibility)
            "plan": parsed_json,          # Parsed JSON object
            "raw_data": {
                "exercises": exercises,
                "recipes": recipes
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"Unexpected error: {str(e)}"
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=error_detail)

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