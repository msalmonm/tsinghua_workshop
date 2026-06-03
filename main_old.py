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
    """Main RAG pipeline endpoint with hybrid architecture:
    - Backend builds structured plan from RAG data
    - LLM generates personalized recommendations and reasoning
    """
    
    # 1. Generate query embedding
    try:
        query_vector = model.encode(request.query).tolist()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating embedding: {str(e)}")
    
    # 2. Retrieve context from Elasticsearch (prioritize FatSecret for recipes)
    exercises = search_elasticsearch("exercises", query_vector, k=10)
    recipes = search_elasticsearch("recipes", query_vector, k=15, boost_fatsecret=True)
    
    # 3. Build plan structure from RAG data
    import json
    
    # Calculate BMI
    bmi = round(request.user_profile.weight_kg / ((request.user_profile.height_cm / 100) ** 2), 2)
    
    # Separate recipes by meal type (simple heuristic based on calories and ready time)
    breakfast_recipes = []
    lunch_recipes = []
    dinner_recipes = []
    
    for recipe in recipes:
        macros = recipe.get('macros', {})
        calories = macros.get('calories', 0)
        ready_time = recipe.get('ready_in_minutes', 30)
        
        # Heuristic: breakfast typically lower calories and quick
        if calories < 400 and ready_time < 30 and len(breakfast_recipes) < 3:
            breakfast_recipes.append(recipe)
        # Lunch: moderate calories
        elif 400 <= calories < 600 and len(lunch_recipes) < 3:
            lunch_recipes.append(recipe)
        # Dinner: can be higher calories
        elif len(dinner_recipes) < 3:
            dinner_recipes.append(recipe)
    
    # Fill missing slots if needed
    remaining_recipes = [r for r in recipes if r not in breakfast_recipes + lunch_recipes + dinner_recipes]
    while len(breakfast_recipes) < 3 and remaining_recipes:
        breakfast_recipes.append(remaining_recipes.pop(0))
    while len(lunch_recipes) < 3 and remaining_recipes:
        lunch_recipes.append(remaining_recipes.pop(0))
    while len(dinner_recipes) < 3 and remaining_recipes:
        dinner_recipes.append(remaining_recipes.pop(0))
    
    # Format meal options
    def format_recipe(recipe):
        macros = recipe.get('macros', {})
        return {
            "recipe_id": recipe.get('id', ''),
            "recipe_name": recipe.get('name', 'Unknown'),
            "description": recipe.get('ingredients', '')[:200],  # First 200 chars
            "image_url": "",
            "recipe_url": "",
            "rating": None,
            "ready_in_minutes": recipe.get('ready_in_minutes'),
            "diet_tags": recipe.get('diets', []),
            "calories": macros.get('calories', 0),
            "protein_g": macros.get('protein_g', 0),
            "carbs_g": macros.get('carbs_g', 0),
            "fats_g": macros.get('fats_g', 0),
            "ingredients": recipe.get('ingredients', ''),
            "instructions": recipe.get('instructions', '')[:300]  # Truncate long instructions
        }
    
    meal_options = {
        "breakfast": [format_recipe(r) for r in breakfast_recipes],
        "lunch": [format_recipe(r) for r in lunch_recipes],
        "dinner": [format_recipe(r) for r in dinner_recipes]
    }
    
    # Format workout options
    def format_exercise(exercise):
        return {
            "exercise_id": exercise.get('id', ''),
            "name": exercise.get('name', 'Unknown'),
            "target_muscle": exercise.get('target_muscle', 'N/A'),
            "secondary_muscles": [],
            "equipment": exercise.get('equipment', 'body weight'),
            "estimated_met": exercise.get('estimated_met'),
            "sets": 3,
            "reps": "8-12",
            "rest_seconds": 90,
            "instructions": exercise.get('instructions', '')[:300]
        }
    
    workout_options = [format_exercise(ex) for ex in exercises[:6]]
    
    # Build weekly calendar (distribute meals across 7 days)
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekly_calendar = []
    
    for i, day in enumerate(days):
        breakfast = breakfast_recipes[i % len(breakfast_recipes)] if breakfast_recipes else {}
        lunch = lunch_recipes[i % len(lunch_recipes)] if lunch_recipes else {}
        dinner = dinner_recipes[i % len(dinner_recipes)] if dinner_recipes else {}
        
        b_macros = breakfast.get('macros', {})
        l_macros = lunch.get('macros', {})
        d_macros = dinner.get('macros', {})
        
        daily_totals = {
            "calories": b_macros.get('calories', 0) + l_macros.get('calories', 0) + d_macros.get('calories', 0),
            "protein_g": round(b_macros.get('protein_g', 0) + l_macros.get('protein_g', 0) + d_macros.get('protein_g', 0), 1),
            "carbs_g": round(b_macros.get('carbs_g', 0) + l_macros.get('carbs_g', 0) + d_macros.get('carbs_g', 0), 1),
            "fats_g": round(b_macros.get('fats_g', 0) + l_macros.get('fats_g', 0) + d_macros.get('fats_g', 0), 1)
        }
        
        # Assign workouts on alternating days (Mon, Wed, Fri)
        is_workout_day = i in [0, 2, 4]  # Monday, Wednesday, Friday
        
        weekly_calendar.append({
            "day": day,
            "breakfast": breakfast.get('name', ''),
            "lunch": lunch.get('name', ''),
            "dinner": dinner.get('name', ''),
            "workout": {
                "focus": exercises[i % len(exercises)].get('target_muscle', '') if is_workout_day and exercises else "Rest day",
                "exercises": [ex.get('name', '') for ex in exercises[i:i+3]] if is_workout_day and exercises else []
            },
            "daily_totals": daily_totals,
            "notes": ""
        })
    
    # Calculate nutrition summary
    total_weekly_cals = sum(day['daily_totals']['calories'] for day in weekly_calendar)
    total_weekly_protein = sum(day['daily_totals']['protein_g'] for day in weekly_calendar)
    total_weekly_carbs = sum(day['daily_totals']['carbs_g'] for day in weekly_calendar)
    total_weekly_fats = sum(day['daily_totals']['fats_g'] for day in weekly_calendar)
    
    avg_daily_cals = round(total_weekly_cals / 7)
    avg_daily_protein = round(total_weekly_protein / 7, 1)
    avg_daily_carbs = round(total_weekly_carbs / 7, 1)
    avg_daily_fats = round(total_weekly_fats / 7, 1)
    
    nutrition_summary = {
        "total_daily_calories_avg": avg_daily_cals,
        "total_daily_protein_g_avg": avg_daily_protein,
        "total_daily_carbs_g_avg": avg_daily_carbs,
        "total_daily_fats_g_avg": avg_daily_fats,
        "macro_notes": ""
    }
    
    # Calculate macro targets (simple heuristics based on goal)
    protein_target = round(request.user_profile.weight_kg * 1.8)  # 1.8g per kg for muscle gain
    calorie_target = round(request.user_profile.weight_kg * 30)  # Rough estimate
    
    macro_bars = [
        {"label": "Calories", "value": avg_daily_cals, "unit": "kcal", "target": calorie_target},
        {"label": "Protein", "value": avg_daily_protein, "unit": "g", "target": protein_target},
        {"label": "Carbs", "value": avg_daily_carbs, "unit": "g", "target": round(calorie_target * 0.4 / 4)},
        {"label": "Fats", "value": avg_daily_fats, "unit": "g", "target": round(calorie_target * 0.3 / 9)}
    ]
    
    
    # 8. Ask LLM only for personalization, tips, and weekly calendar assignment
    llm_prompt = f"""You are a fitness and nutrition expert. Generate ONLY personalized recommendations and weekly calendar.

User Profile:
- Age: {request.user_profile.age}, Sex: {request.user_profile.sex}
- Weight: {request.user_profile.weight_kg}kg, Height: {request.user_profile.height_cm}cm, BMI: {bmi:.1f}
- Goal: {request.query}

Available meal options: {len(meal_options['breakfast'])} breakfast, {len(meal_options['lunch'])} lunch, {len(meal_options['dinner'])} dinner
Available exercises: {len(workout_options)}

CRITICAL: Respond in the SAME LANGUAGE as the user's goal query.

Return ONLY this JSON structure:
{{
  "plan_summary": {{
    "title": "Brief title in user's language",
    "goal_detected": "Main goal",
    "short_summary": "1-2 sentence summary",
    "focus": "Main focus area",
    "difficulty_level": "Beginner/Intermediate/Advanced"
  }},
  "weekly_calendar": [
    {{
      "day": "Monday",
      "breakfast_index": 0,
      "lunch_index": 0,
      "dinner_index": 0,
      "workout_exercise_indices": [0, 1, 2],
      "workout_focus": "Upper body" or "Rest day",
      "notes": "Brief daily tip"
    }}
  ],
  "ai_recommendations": {{
    "main_tip": "One key recommendation",
    "personalized_notes": ["Note 1", "Note 2"],
    "nutrition_tips": ["Tip 1", "Tip 2"],
    "workout_tips": ["Tip 1", "Tip 2"],
    "safety_notes": ["Safety note 1"]
  }}
}}

Rules:
1. Create 7 days (Monday-Sunday) in weekly_calendar
2. Use indices to reference meals (0-2) and exercises (0-5)
3. Suggest 3 workout days per week (or as user requested)
4. Rest days: workout_exercise_indices=[], workout_focus="Rest day"
5. Keep all text concise (1-2 sentences max)
6. Respond in the user's query language"""

    # Try GPT-5.4-mini first, fallback to GPT-4o-mini
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
                    {"role": "user", "content": llm_prompt}
                ],
                "model": model_config["name"],
                "temperature": 0.7,
                model_config["max_param"]: 3000,  # Much less needed now - only tips and calendar
                "response_format": {"type": "json_object"}
            }
            
            chat_completion = openai_client.chat.completions.create(**params)
            final_response = chat_completion.choices[0].message.content
            print(f"✓ Successfully used model: {model_config['name']}")
            print(f"  Response length: {len(final_response)} chars")
            break
            
        except Exception as e:
            last_error = e
            print(f"✗ Model {model_config['name']} failed: {str(e)}")
            if model_config == models_to_try[-1]:
                import traceback
                error_detail = f"All models failed. Last error: {str(e)}"
                print(f"Traceback: {traceback.format_exc()}")
                raise HTTPException(status_code=500, detail=error_detail)
            continue
    
    if not final_response:
        raise HTTPException(status_code=500, detail=f"No model succeeded. Last error: {str(last_error)}")
    
    # 9. Parse LLM response
    import json
    try:
        llm_data = json.loads(final_response)
    except json.JSONDecodeError as e:
        print(f"✗ JSON parsing failed: {str(e)}")
        print(f"Response preview (first 500 chars): {final_response[:500]}")
        raise HTTPException(status_code=500, detail=f"OpenAI returned invalid JSON: {str(e)}")
    
    # 10. Expand weekly calendar with actual meal/exercise data
    weekly_calendar_expanded = []
    for day_plan in llm_data.get('weekly_calendar', []):
        b_idx = day_plan.get('breakfast_index', 0)
        l_idx = day_plan.get('lunch_index', 0)
        d_idx = day_plan.get('dinner_index', 0)
        
        selected_breakfast = meal_options['breakfast'][b_idx] if b_idx < len(meal_options['breakfast']) else meal_options['breakfast'][0]
        selected_lunch = meal_options['lunch'][l_idx] if l_idx < len(meal_options['lunch']) else meal_options['lunch'][0]
        selected_dinner = meal_options['dinner'][d_idx] if d_idx < len(meal_options['dinner']) else meal_options['dinner'][0]
        
        daily_total_cal = selected_breakfast['calories'] + selected_lunch['calories'] + selected_dinner['calories']
        daily_total_pro = selected_breakfast['protein_g'] + selected_lunch['protein_g'] + selected_dinner['protein_g']
        daily_total_carbs = selected_breakfast['carbs_g'] + selected_lunch['carbs_g'] + selected_dinner['carbs_g']
        daily_total_fats = selected_breakfast['fats_g'] + selected_lunch['fats_g'] + selected_dinner['fats_g']
        
        exercise_indices = day_plan.get('workout_exercise_indices', [])
        selected_exercises = [workout_options[i] for i in exercise_indices if i < len(workout_options)]
        
        weekly_calendar_expanded.append({
            "day": day_plan.get('day', ''),
            "breakfast": selected_breakfast['recipe_name'],
            "lunch": selected_lunch['recipe_name'],
            "dinner": selected_dinner['recipe_name'],
            "workout": {
                "focus": day_plan.get('workout_focus', 'Rest day'),
                "exercises": [ex['name'] for ex in selected_exercises]
            },
            "daily_totals": {
                "calories": int(daily_total_cal),
                "protein_g": round(daily_total_pro, 1),
                "carbs_g": round(daily_total_carbs, 1),
                "fats_g": round(daily_total_fats, 1)
            },
            "notes": day_plan.get('notes', '')
        })
    
    # 11. Build final response combining RAG data + LLM personalization
    complete_plan = {
        "plan_summary": llm_data.get('plan_summary', {}),
        "user_profile_summary": user_profile_summary,
        "nutrition_summary": nutrition_summary,
        "macro_bars": macro_bars,
        "meal_options": meal_options,
        "workout_options": workout_options,
        "weekly_calendar": weekly_calendar_expanded,
        "ai_recommendations": llm_data.get('ai_recommendations', {}),
        "retrieved_data_summary": {
            "recipes_used": len(recipes),
            "exercises_used": len(exercises),
            "source": "Elasticsearch k-NN with FatSecret prioritization"
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