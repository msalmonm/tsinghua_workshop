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
    
    # 3. Calculate nutritional targets (Senior Nutritionist logic)
    # Base caloric needs by sex
    base_calories = 2000 if request.user_profile.sex.lower() in ['male', 'hombre', 'm'] else 1800
    
    # Adjust based on goal detection (smart parsing)
    goal_lower = request.query.lower()
    
    # Goal classification with mixed goal detection
    has_weight_loss = any(word in goal_lower for word in ['perder', 'bajar', 'lose', 'weight loss', 'adelgazar', 'reducir', 'grasa', 'fat'])
    has_muscle_gain = any(word in goal_lower for word in ['ganar', 'aumentar', 'bulk', 'masa', 'gain', 'muscle', 'músculo', 'muscular'])
    
    if has_weight_loss and has_muscle_gain:
        # Mixed goals = body recomposition
        goal_type = 'recomp'
        calorie_adjustment = -0.10  # Slight deficit
        protein_multiplier = 2.2  # Very high protein for recomp
    elif has_weight_loss:
        goal_type = 'weight_loss'
        calorie_adjustment = -0.20  # 20% deficit
        protein_multiplier = 2.0  # High protein to preserve muscle
    elif has_muscle_gain:
        goal_type = 'muscle_gain'
        calorie_adjustment = 0.15  # 15% surplus
        protein_multiplier = 1.8
    elif any(word in goal_lower for word in ['mantener', 'maintain', 'tonificar', 'tone']):
        goal_type = 'maintenance'
        calorie_adjustment = 0.0  # Maintenance
        protein_multiplier = 1.6
    else:
        # Default to maintenance if unclear
        goal_type = 'maintenance'
        calorie_adjustment = 0.0
        protein_multiplier = 1.6
    
    # Calculate target calories
    target_calories = int(base_calories * (1 + calorie_adjustment))
    
    # Protein target: g per kg body weight
    target_protein_g = int(request.user_profile.weight_kg * protein_multiplier)
    
    # Fat target: 25-30% of calories
    target_fats_g = int((target_calories * 0.275) / 9)  # 9 cal per g of fat
    
    # Carbs: remaining calories
    protein_calories = target_protein_g * 4
    fat_calories = target_fats_g * 9
    target_carbs_g = int((target_calories - protein_calories - fat_calories) / 4)
    
    # BMI for context
    bmi = request.user_profile.weight_kg / ((request.user_profile.height_cm / 100) ** 2)
    
    # Debug logging
    print(f"\n🧮 Nutritional Targets Calculated:")
    print(f"   Goal Type: {goal_type}")
    print(f"   Base Calories: {base_calories} → Target: {target_calories} ({calorie_adjustment:+.0%})")
    print(f"   Protein: {target_protein_g}g ({protein_multiplier}x body weight)")
    print(f"   Carbs: {target_carbs_g}g | Fats: {target_fats_g}g")
    # 4. Build user profile summary
    user_profile_summary = {
        "age": request.user_profile.age,
        "sex": request.user_profile.sex,
        "weight_kg": request.user_profile.weight_kg,
        "height_cm": request.user_profile.height_cm,
        "bmi": round(bmi, 2),
        "goal_type": goal_type,
        "target_calories": target_calories,
        "target_protein_g": target_protein_g,
        "target_carbs_g": target_carbs_g,
        "target_fats_g": target_fats_g
    }
    
    # 5. Categorize recipes by meal type AND calorie targets
    # Breakfast: 25-30% of daily calories
    # Lunch: 35-40% of daily calories  
    # Dinner: 30-35% of daily calories
    breakfast_target = target_calories * 0.275
    lunch_target = target_calories * 0.375
    dinner_target = target_calories * 0.35
    
    breakfast_recipes = []
    lunch_recipes = []
    dinner_recipes = []
    
    for recipe in recipes:
        calories = recipe.get('macros', {}).get('calories', 0)
        ready_time = recipe.get('ready_in_minutes', 30)
        
        # Smart categorization based on calories and timing
        if abs(calories - breakfast_target) < 200 and len(breakfast_recipes) < 3:
            breakfast_recipes.append(recipe)
        elif abs(calories - lunch_target) < 250 and len(lunch_recipes) < 3:
            lunch_recipes.append(recipe)
        elif abs(calories - dinner_target) < 250 and len(dinner_recipes) < 3:
            dinner_recipes.append(recipe)
        # Fallback: use calorie ranges
        elif calories < breakfast_target + 100 and len(breakfast_recipes) < 3:
            breakfast_recipes.append(recipe)
        elif breakfast_target < calories < lunch_target + 100 and len(lunch_recipes) < 3:
            lunch_recipes.append(recipe)
        elif calories >= lunch_target and len(dinner_recipes) < 3:
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
    
    # 8. Build macro bars with smart targets
    macro_bars = [
        {"label": "Calories", "value": total_cal, "unit": "kcal", "target": target_calories},
        {"label": "Protein", "value": total_pro, "unit": "g", "target": target_protein_g},
        {"label": "Carbs", "value": total_carbs, "unit": "g", "target": target_carbs_g},
        {"label": "Fats", "value": total_fats, "unit": "g", "target": target_fats_g}
    ]
    
    # 9. Ask LLM for personalization with nutritionist context
    llm_prompt = f"""You are a SENIOR NUTRITIONIST and fitness expert. Generate personalized recommendations.

User Profile:
- {request.user_profile.age}y {request.user_profile.sex}, {request.user_profile.weight_kg}kg, {request.user_profile.height_cm}cm
- BMI: {bmi:.1f}
- Goal: {request.query}
- Goal Type Detected: {goal_type}

NUTRITIONAL TARGETS (calculated by senior nutritionist):
- Daily Calories: {target_calories} kcal ({base_calories} base + {calorie_adjustment:+.0%} adjustment)
- Protein: {target_protein_g}g ({protein_multiplier}g/kg body weight)
- Carbs: {target_carbs_g}g
- Fats: {target_fats_g}g

Available Resources:
- {len(meal_options['breakfast'])} breakfast options (~{int(breakfast_target)} cal each)
- {len(meal_options['lunch'])} lunch options (~{int(lunch_target)} cal each)
- {len(meal_options['dinner'])} dinner options (~{int(dinner_target)} cal each)
- {len(workout_options)} exercises

CRITICAL INSTRUCTIONS:
1. Respond in the SAME LANGUAGE as the user's goal query
2. Consider the nutritional targets when assigning meals
3. Distribute meals to meet daily calorie target
4. Prioritize protein-rich options for muscle goals
5. Suggest appropriate workout frequency for goal type

Return JSON:
{{
  "plan_summary": {{
    "title": "Brief title in user's language",
    "goal_detected": "{goal_type}",
    "short_summary": "1-2 sentence summary considering nutritional science",
    "focus": "Main nutritional focus",
    "difficulty_level": "Beginner/Intermediate/Advanced"
  }},
  "weekly_calendar": [
    {{"day": "Monday", "breakfast_index": 0, "lunch_index": 0, "dinner_index": 0, "workout_exercise_indices": [0,1,2], "workout_focus": "Upper body", "notes": "Brief tip"}}
  ],
  "ai_recommendations": {{
    "main_tip": "Key nutritional advice",
    "personalized_notes": ["Note about their BMI/goals", "Hydration tip"],
    "nutrition_tips": ["Macro distribution tip", "Meal timing tip"],
    "workout_tips": ["Training frequency for goal", "Recovery tip"],
    "safety_notes": ["Important safety consideration"]
  }}
}}

Rules: 7 days, use indices 0-2 for meals and 0-5 for exercises, suggest workout days based on goal (weight_loss=4-5 days, muscle_gain=4 days, maintenance=3 days, recomp=5 days), rest days have workout_exercise_indices=[]"""

    # Try models (gpt-4o-mini first as primary, more stable and widely available)
    models_to_try = [
        {"name": "gpt-4o-mini", "max_param": "max_tokens"},
        {"name": "gpt-5.4-mini", "max_param": "max_completion_tokens"}
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
