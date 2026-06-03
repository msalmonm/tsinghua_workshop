#!/usr/bin/env python3
"""
RAG Health & Fitness API - Hybrid Architecture
Python builds JSON from RAG data + LLM adds personalization only
"""

import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer
from openai import OpenAI
import json

load_dotenv()
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
app = FastAPI(title="Fitness RAG API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    plan: dict
    raw_data: dict

def search_elasticsearch(index_name: str, query_vector: list, k: int = 3, boost_fatsecret: bool = False):
    """k-NN search with optional FatSecret prioritization"""
    search_query = {
        "knn": {
            "field": "embedding",
            "query_vector": query_vector,
            "k": k * 3 if boost_fatsecret else k,
            "num_candidates": 100 if boost_fatsecret else 50
        },
        "_source": ["search_context"]
    }
    
    try:
        response = es_client.search(index=index_name, body=search_query)
        results = []
        
        for hit in response["hits"]["hits"]:
            try:
                parsed_data = json.loads(hit["_source"]["search_context"])
                parsed_data["_score"] = hit["_score"]
                results.append(parsed_data)
            except:
                fallback_data = hit["_source"]
                fallback_data["_score"] = hit["_score"]
                results.append(fallback_data)
        
        # Prioritize FatSecret recipes
        if boost_fatsecret and index_name == "recipes":
            fatsecret_recipes = [r for r in results if r.get("id", "").startswith("rec_fs_")]
            other_recipes = [r for r in results if not r.get("id", "").startswith("rec_fs_")]
            results = (fatsecret_recipes + other_recipes)[:k]
        else:
            results = results[:k]
        
        return results
    except Exception as e:
        print(f"Error searching {index_name}: {e}")
        return []

@app.get("/health")
def health_check():
    return {
        "status": "active",
        "message": "RAG API v2 is running (Hybrid: RAG + LLM)",
        "elasticsearch": "connected" if es_client.ping() else "disconnected"
    }

@app.post("/api/recommend", response_model=RecommendationResponse)
def get_recommendation(request: QueryRequest):
    """Hybrid RAG: Python builds JSON from RAG + LLM adds personalization"""
    
    # 1. Generate query embedding
    try:
        query_vector = model.encode(request.query).tolist()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating embedding: {str(e)}")
    
    # 2. Retrieve from Elasticsearch
    exercises = search_elasticsearch("exercises", query_vector, k=10)
    recipes = search_elasticsearch("recipes", query_vector, k=15, boost_fatsecret=True)
    
    # 3. Build user profile summary
    bmi = request.user_profile.weight_kg / ((request.user_profile.height_cm / 100) ** 2)
    user_profile_summary = {
        "age": request.user_profile.age,
        "sex": request.user_profile.sex,
        "weight_kg": request.user_profile.weight_kg,
        "height_cm": request.user_profile.height_cm,
        "bmi": round(bmi, 2)
    }
    
    # 4. Categorize recipes (simple heuristic)
    breakfast_recipes = []
    lunch_recipes = []
    dinner_recipes = []
    
    for recipe in recipes:
        calories = recipe.get('macros', {}).get('calories', 0)
        ready_time = recipe.get('ready_in_minutes', 30)
        
        if calories < 400 and ready_time < 30 and len(breakfast_recipes) < 3:
            breakfast_recipes.append(recipe)
        elif 400 <= calories < 600 and len(lunch_recipes) < 3:
            lunch_recipes.append(recipe)
        elif len(dinner_recipes) < 3:
            dinner_recipes.append(recipe)
    
    # Fill missing slots
    remaining = [r for r in recipes if r not in breakfast_recipes + lunch_recipes + dinner_recipes]
    while len(breakfast_recipes) < 3 and remaining:
        breakfast_recipes.append(remaining.pop(0))
    while len(lunch_recipes) < 3 and remaining:
        lunch_recipes.append(remaining.pop(0))
    while len(dinner_recipes) < 3 and remaining:
        dinner_recipes.append(remaining.pop(0))
    
    # 5. Format meal options
    def format_recipe(recipe):
        return {
            "recipe_id": recipe.get('id', ''),
            "recipe_name": recipe.get('name', ''),
            "ready_in_minutes": recipe.get('ready_in_minutes'),
            "diet_tags": recipe.get('diets', []),
            "calories": recipe.get('macros', {}).get('calories', 0),
            "protein_g": recipe.get('macros', {}).get('protein_g', 0),
            "carbs_g": recipe.get('macros', {}).get('carbs_g', 0),
            "fats_g": recipe.get('macros', {}).get('fats_g', 0),
            "ingredients": recipe.get('ingredients', ''),
            "instructions": recipe.get('instructions', '')
        }
    
    meal_options = {
        "breakfast": [format_recipe(r) for r in breakfast_recipes],
        "lunch": [format_recipe(r) for r in lunch_recipes],
        "dinner": [format_recipe(r) for r in dinner_recipes]
    }
    
    # 6. Format workout options
    def format_exercise(exercise):
        return {
            "exercise_id": exercise.get('id', ''),
            "name": exercise.get('name', ''),
            "target_muscle": exercise.get('target_muscle', ''),
            "equipment": exercise.get('equipment', ''),
            "estimated_met": exercise.get('estimated_met'),
            "instructions": exercise.get('instructions', '')
        }
    
    workout_options = [format_exercise(ex) for ex in exercises[:6]]
    
    # 7. Calculate nutrition summary
    sample_day = [
        meal_options['breakfast'][0],
        meal_options['lunch'][0],
        meal_options['dinner'][0]
    ]
    
    total_cal = sum(m['calories'] for m in sample_day)
    total_pro = sum(m['protein_g'] for m in sample_day)
    total_carbs = sum(m['carbs_g'] for m in sample_day)
    total_fats = sum(m['fats_g'] for m in sample_day)
    
    nutrition_summary = {
        "total_daily_calories_avg": int(total_cal),
        "total_daily_protein_g_avg": round(total_pro, 1),
        "total_daily_carbs_g_avg": round(total_carbs, 1),
        "total_daily_fats_g_avg": round(total_fats, 1)
    }
    
    # 8. Build macro bars
    macro_bars = [
        {"label": "Calories", "value": total_cal, "unit": "kcal", "target": 2000},
        {"label": "Protein", "value": total_pro, "unit": "g", "target": int(request.user_profile.weight_kg * 1.6)},
        {"label": "Carbs", "value": total_carbs, "unit": "g", "target": 200},
        {"label": "Fats", "value": total_fats, "unit": "g", "target": 65}
    ]
    
    # 9. Ask LLM for personalization ONLY
    llm_prompt = f"""You are a fitness expert. Generate personalized recommendations and weekly calendar.

User: {request.user_profile.age}y {request.user_profile.sex}, {request.user_profile.weight_kg}kg, {request.user_profile.height_cm}cm (BMI: {bmi:.1f})
Goal: {request.query}

Available: {len(meal_options['breakfast'])} breakfast, {len(meal_options['lunch'])} lunch, {len(meal_options['dinner'])} dinner options + {len(workout_options)} exercises

CRITICAL: Respond in SAME LANGUAGE as goal query.

Return JSON:
{{
  "plan_summary": {{"title": "", "goal_detected": "", "short_summary": "", "focus": "", "difficulty_level": ""}},
  "weekly_calendar": [
    {{"day": "Monday", "breakfast_index": 0, "lunch_index": 0, "dinner_index": 0, "workout_exercise_indices": [0,1,2], "workout_focus": "Upper body", "notes": ""}}
  ],
  "ai_recommendations": {{"main_tip": "", "personalized_notes": [], "nutrition_tips": [], "workout_tips": [], "safety_notes": []}}
}}

Rules: 7 days, use indices 0-2 for meals and 0-5 for exercises, suggest 3 workout days, rest days have workout_exercise_indices=[], be concise"""

    # Try models
    models_to_try = [
        {"name": "gpt-5.4-mini", "max_param": "max_completion_tokens"},
        {"name": "gpt-4o-mini", "max_param": "max_tokens"}
    ]
    
    llm_data = None
    for model_config in models_to_try:
        try:
            params = {
                "messages": [{"role": "user", "content": llm_prompt}],
                "model": model_config["name"],
                "temperature": 0.7,
                model_config["max_param"]: 3000,
                "response_format": {"type": "json_object"}
            }
            
            chat_completion = openai_client.chat.completions.create(**params)
            response_text = chat_completion.choices[0].message.content
            print(f"✓ Model: {model_config['name']}, Length: {len(response_text)} chars")
            
            llm_data = json.loads(response_text)
            break
        except Exception as e:
            print(f"✗ {model_config['name']}: {e}")
            if model_config == models_to_try[-1]:
                raise HTTPException(status_code=500, detail=f"All models failed: {str(e)}")
    
    if not llm_data:
        raise HTTPException(status_code=500, detail="No LLM response")
    
    # 10. Expand weekly calendar with actual data
    weekly_calendar = []
    for day_plan in llm_data.get('weekly_calendar', []):
        b_idx = min(day_plan.get('breakfast_index', 0), len(meal_options['breakfast']) - 1)
        l_idx = min(day_plan.get('lunch_index', 0), len(meal_options['lunch']) - 1)
        d_idx = min(day_plan.get('dinner_index', 0), len(meal_options['dinner']) - 1)
        
        b = meal_options['breakfast'][b_idx]
        l = meal_options['lunch'][l_idx]
        d = meal_options['dinner'][d_idx]
        
        daily_cal = b['calories'] + l['calories'] + d['calories']
        daily_pro = b['protein_g'] + l['protein_g'] + d['protein_g']
        daily_carbs = b['carbs_g'] + l['carbs_g'] + d['carbs_g']
        daily_fats = b['fats_g'] + l['fats_g'] + d['fats_g']
        
        ex_indices = day_plan.get('workout_exercise_indices', [])
        selected_exercises = [workout_options[i]['name'] for i in ex_indices if i < len(workout_options)]
        
        weekly_calendar.append({
            "day": day_plan.get('day', ''),
            "breakfast": b['recipe_name'],
            "lunch": l['recipe_name'],
            "dinner": d['recipe_name'],
            "workout": {
                "focus": day_plan.get('workout_focus', 'Rest day'),
                "exercises": selected_exercises
            },
            "daily_totals": {
                "calories": int(daily_cal),
                "protein_g": round(daily_pro, 1),
                "carbs_g": round(daily_carbs, 1),
                "fats_g": round(daily_fats, 1)
            },
            "notes": day_plan.get('notes', '')
        })
    
    # 11. Build complete response
    complete_plan = {
        "plan_summary": llm_data.get('plan_summary', {}),
        "user_profile_summary": user_profile_summary,
        "nutrition_summary": nutrition_summary,
        "macro_bars": macro_bars,
        "meal_options": meal_options,
        "workout_options": workout_options,
        "weekly_calendar": weekly_calendar,
        "ai_recommendations": llm_data.get('ai_recommendations', {}),
        "retrieved_data_summary": {
            "recipes_used": len(recipes),
            "exercises_used": len(exercises),
            "source": "Elasticsearch k-NN + FatSecret priority"
        }
    }
    
    return {
        "response": json.dumps(complete_plan, ensure_ascii=False),
        "plan": complete_plan,
        "raw_data": {
            "exercises": exercises,
            "recipes": recipes
        }
    }

@app.get("/")
def root():
    return {
        "name": "Fitness RAG API v2",
        "version": "2.0.0",
        "architecture": "Hybrid: Python builds JSON from RAG + LLM adds personalization",
        "endpoints": {
            "health": "/health",
            "recommend": "/api/recommend (POST)",
            "docs": "/docs"
        }
    }
