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
    activity_level: str = "moderately_active"  # sedentary, lightly_active, moderately_active, very_active, extra_active

class QueryRequest(BaseModel):
    query: str
    user_profile: UserProfile

class RecommendationResponse(BaseModel):
    response: str
    plan: dict
    raw_data: dict

# ========================================
# NUTRITION CALCULATION HELPERS
# ========================================

def calculate_bmr(weight_kg: float, height_cm: float, age: int, sex: str) -> float:
    """
    Calculate Basal Metabolic Rate using Mifflin-St Jeor equation.
    
    Male: BMR = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    Female: BMR = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    """
    sex_normalized = sex.lower()
    if sex_normalized in ['male', 'hombre', 'm', 'man']:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:  # female, mujer, f, woman
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    return round(bmr, 2)


def get_activity_factor(activity_level: str) -> float:
    """
    Convert activity level string to TDEE multiplier.
    """
    activity_factors = {
        "sedentary": 1.2,
        "lightly_active": 1.375,
        "moderately_active": 1.55,
        "very_active": 1.725,
        "extra_active": 1.9
    }
    return activity_factors.get(activity_level.lower(), 1.55)  # default to moderately_active


def calculate_tdee(bmr: float, activity_factor: float) -> int:
    """
    Calculate Total Daily Energy Expenditure.
    
    TDEE = BMR * activity_factor
    """
    return int(bmr * activity_factor)


def classify_goal(query: str) -> tuple:
    """
    Classify user goal from query text.
    
    Returns: (goal_type, calorie_adjustment, protein_multiplier)
    """
    goal_lower = query.lower()
    
    # Goal classification with mixed goal detection
    has_weight_loss = any(word in goal_lower for word in [
        'perder', 'bajar', 'lose', 'weight loss', 'adelgazar', 'reducir', 'grasa', 'fat', 'cut', 'deficit'
    ])
    has_muscle_gain = any(word in goal_lower for word in [
        'ganar', 'aumentar', 'bulk', 'masa', 'gain', 'muscle', 'músculo', 'muscular', 'hypertrophy'
    ])
    
    if has_weight_loss and has_muscle_gain:
        # Mixed goals = body recomposition
        return ('recomp', -0.10, 2.2)
    elif has_weight_loss:
        return ('weight_loss', -0.20, 2.0)
    elif has_muscle_gain:
        return ('muscle_gain', 0.15, 1.8)
    elif any(word in goal_lower for word in ['mantener', 'maintain', 'tonificar', 'tone']):
        return ('maintenance', 0.0, 1.6)
    else:
        # Default to maintenance if unclear
        return ('maintenance', 0.0, 1.6)


def apply_goal_adjustment(tdee: int, calorie_adjustment: float) -> int:
    """
    Apply goal-based calorie adjustment to TDEE.
    
    Adjustments:
    - weight_loss: -20%
    - recomp: -10%
    - maintenance: 0%
    - muscle_gain: +15%
    """
    return int(tdee * (1 + calorie_adjustment))


def detect_unsafe_goal(query: str, target_calories: int, sex: str, tdee: int) -> tuple:
    """
    Detect unsafe or extreme goals and enforce safety minimums.
    
    Returns: (is_unsafe, adjusted_calories, warnings)
    """
    warnings = []
    is_unsafe = False
    adjusted_calories = target_calories
    
    # Set minimum safe calories
    sex_normalized = sex.lower()
    min_calories = 1500 if sex_normalized in ['male', 'hombre', 'm', 'man'] else 1200
    
    # Check for extreme language in query
    query_lower = query.lower()
    extreme_phrases = [
        'lose 10', 'lose 20', 'perder 10', 'perder 20',
        'in 2 weeks', 'en 2 semanas', 'in 1 week', 'en 1 semana',
        'crash', 'extreme', 'fast', 'rapid', 'rapido', 'extremo',
        'starvation', 'starve', 'purge', 'hambre'
    ]
    
    if any(phrase in query_lower for phrase in extreme_phrases):
        is_unsafe = True
        warnings.append("Your goal may be too aggressive. Safe weight loss is 0.5-1kg per week.")
    
    # Check if target calories are below safety minimum
    if target_calories < min_calories:
        is_unsafe = True
        adjusted_calories = min_calories
        warnings.append(
            f"Target calories ({target_calories} kcal) adjusted to safe minimum ({min_calories} kcal). "
            f"Consult a licensed nutritionist for very low calorie diets."
        )
    
    # Check for excessive deficit (>25% of TDEE)
    deficit_pct = (tdee - target_calories) / tdee if tdee > 0 else 0
    if deficit_pct > 0.25:
        is_unsafe = True
        adjusted_calories = max(int(tdee * 0.75), min_calories)
        warnings.append(
            f"Calorie deficit too large ({int(deficit_pct*100)}%). Adjusted to 25% maximum deficit. "
            f"Extreme deficits can harm metabolism and muscle mass."
        )
    
    # Check for excessive surplus (>20% of TDEE) for muscle gain
    surplus_pct = (target_calories - tdee) / tdee if tdee > 0 else 0
    if surplus_pct > 0.20:
        is_unsafe = True
        adjusted_calories = int(tdee * 1.20)
        warnings.append(
            f"Calorie surplus too large ({int(surplus_pct*100)}%). Adjusted to 20% maximum. "
            f"Excessive surplus leads to unnecessary fat gain."
        )
    
    return (is_unsafe, adjusted_calories, warnings)


def validate_nutrition_plan(
    daily_totals: list,
    target_calories: int,
    target_protein_g: int,
    all_meal_options: list,
    all_snack_options: list
) -> dict:
    """
    Validate that the LLM-generated plan meets nutritional targets.
    Calculate actual macros from recipe indices and portions.
    
    Returns validation results with warnings and adjustments.
    """
    warnings = []
    calories_within_range = True
    protein_sufficient = True
    
    # Recalculate actual daily totals from recipe data
    recalculated_days = []
    
    for day in daily_totals:
        day_cal = 0
        day_pro = 0
        day_carbs = 0
        day_fats = 0
        
        for meal in day.get('meals', []):
            recipe_indices = meal.get('recipe_indices', [])
            portion_multipliers = meal.get('portion_multipliers', [1.0] * len(recipe_indices))
            
            for idx, multiplier in zip(recipe_indices, portion_multipliers):
                # Determine if it's a meal or snack
                is_snack = meal.get('meal_type', '').lower() in ['snack', 'morning snack', 'afternoon snack', 'evening snack']
                recipe_list = all_snack_options if is_snack else all_meal_options
                
                if 0 <= idx < len(recipe_list):
                    recipe = recipe_list[idx]
                    day_cal += int(recipe['base_calories'] * multiplier)
                    day_pro += recipe['base_protein_g'] * multiplier
                    day_carbs += recipe['base_carbs_g'] * multiplier
                    day_fats += recipe['base_fats_g'] * multiplier
        
        recalculated_days.append({
            'calories': day_cal,
            'protein_g': round(day_pro, 1),
            'carbs_g': round(day_carbs, 1),
            'fats_g': round(day_fats, 1)
        })
    
    # Calculate average
    if recalculated_days:
        avg_cal = int(sum(d['calories'] for d in recalculated_days) / len(recalculated_days))
        avg_pro = round(sum(d['protein_g'] for d in recalculated_days) / len(recalculated_days), 1)
        avg_carbs = round(sum(d['carbs_g'] for d in recalculated_days) / len(recalculated_days), 1)
        avg_fats = round(sum(d['fats_g'] for d in recalculated_days) / len(recalculated_days), 1)
    else:
        avg_cal = avg_pro = avg_carbs = avg_fats = 0
        warnings.append("No meal data to validate")
    
    # Validate calories (±5% tolerance)
    calorie_tolerance = target_calories * 0.05
    if abs(avg_cal - target_calories) > calorie_tolerance:
        calories_within_range = False
        diff_pct = int(((avg_cal - target_calories) / target_calories) * 100)
        warnings.append(
            f"Calories off target: {avg_cal} kcal vs {target_calories} kcal target ({diff_pct:+d}%). "
            f"Consider adjusting portion sizes."
        )
    
    # Validate protein (minimum 90% of target)
    protein_threshold = target_protein_g * 0.90
    if avg_pro < protein_threshold:
        protein_sufficient = False
        shortfall_pct = int(((avg_pro - target_protein_g) / target_protein_g) * 100)
        warnings.append(
            f"Protein below target: {avg_pro}g vs {target_protein_g}g target ({shortfall_pct:+d}%). "
            f"Add higher-protein recipes or increase portions."
        )
    
    return {
        "calories_within_range": calories_within_range,
        "protein_sufficient": protein_sufficient,
        "warnings": warnings,
        "recalculated_macros": {
            "avg_daily_calories": avg_cal,
            "avg_daily_protein_g": avg_pro,
            "avg_daily_carbs_g": avg_carbs,
            "avg_daily_fats_g": avg_fats
        }
    }

# ========================================

def search_elasticsearch(index_name: str, query_vector: list, k: int = 3, filter_zero_macros: bool = False):
    """k-NN search with automatic FatSecret filtering and zero-macro removal"""
    search_query = {
        "knn": {
            "field": "embedding",
            "query_vector": query_vector,
            "k": k * 4,  # Retrieve more to allow filtering
            "num_candidates": 150
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
        
        # Filter zero-macro recipes (TheMealDB recipes with no nutritional data)
        if filter_zero_macros and index_name == "recipes":
            results = [r for r in results if r.get("macros", {}).get("calories", 0) > 0]
            print(f"   Filtered to {len(results)} recipes with valid macros (removed zero-macro recipes)")
        
        # Prioritize FatSecret recipes
        if index_name == "recipes":
            fatsecret_recipes = [r for r in results if r.get("id", "").startswith("rec_fs_")]
            other_recipes = [r for r in results if not r.get("id", "").startswith("rec_fs_")]
            results = fatsecret_recipes + other_recipes
        
        return results[:k]
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
    
    # 2. Retrieve from Elasticsearch (MORE data for better selection)
    exercises = search_elasticsearch("exercises", query_vector, k=12)
    
    # Get diverse recipes: main meals + snacks
    main_recipes = search_elasticsearch("recipes", query_vector, k=30, filter_zero_macros=True)
    snack_query_vector = model.encode("healthy snacks protein bars fruits nuts yogurt").tolist()
    snack_recipes = search_elasticsearch("recipes", snack_query_vector, k=15, filter_zero_macros=True)
    
    # Combine and deduplicate
    all_recipes_dict = {r['id']: r for r in main_recipes + snack_recipes}
    recipes = list(all_recipes_dict.values())
    
    print(f"\n📦 Retrieved: {len(recipes)} recipes (all with macros), {len(exercises)} exercises")
    
    # 3. Calculate nutritional targets using BMR + TDEE (Professional Nutritionist Method)
    
    # Step 1: Calculate BMR (Basal Metabolic Rate)
    bmr = calculate_bmr(
        request.user_profile.weight_kg,
        request.user_profile.height_cm,
        request.user_profile.age,
        request.user_profile.sex
    )
    
    # Step 2: Get activity factor
    activity_factor = get_activity_factor(request.user_profile.activity_level)
    
    # Step 3: Calculate TDEE (Total Daily Energy Expenditure)
    tdee = calculate_tdee(bmr, activity_factor)
    
    # Step 4: Classify goal and get adjustments
    goal_type, calorie_adjustment, protein_multiplier = classify_goal(request.query)
    
    # Step 5: Apply goal adjustment to get target calories
    target_calories_initial = apply_goal_adjustment(tdee, calorie_adjustment)
    
    # Step 6: Safety check and adjust if needed
    is_unsafe, target_calories, safety_warnings = detect_unsafe_goal(
        request.query,
        target_calories_initial,
        request.user_profile.sex,
        tdee
    )
    
    # Step 7: Calculate macronutrient targets
    # Protein target: g per kg body weight
    target_protein_g = int(request.user_profile.weight_kg * protein_multiplier)
    
    # Fat target: 25-30% of calories (we use 27.5%)
    target_fats_g = int((target_calories * 0.275) / 9)  # 9 cal per g of fat
    
    # Carbs: remaining calories
    protein_calories = target_protein_g * 4
    fat_calories = target_fats_g * 9
    target_carbs_g = int((target_calories - protein_calories - fat_calories) / 4)
    
    # BMI for context
    bmi = request.user_profile.weight_kg / ((request.user_profile.height_cm / 100) ** 2)
    
    print(f"\n🧮 Nutritional Targets (BMR/TDEE Method):")
    print(f"   BMR: {bmr} kcal | TDEE: {tdee} kcal (activity: {request.user_profile.activity_level})")
    print(f"   Goal: {goal_type} | Target: {target_calories} kcal ({calorie_adjustment:+.0%})")
    print(f"   Protein: {target_protein_g}g | Carbs: {target_carbs_g}g | Fats: {target_fats_g}g")
    if is_unsafe:
        print(f"   ⚠️ Safety adjustments applied: {len(safety_warnings)} warnings")
    # 4. Build user profile summary
    user_profile_summary = {
        "age": request.user_profile.age,
        "sex": request.user_profile.sex,
        "weight_kg": request.user_profile.weight_kg,
        "height_cm": request.user_profile.height_cm,
        "bmi": round(bmi, 2),
        "activity_level": request.user_profile.activity_level,
        "bmr": bmr,
        "tdee": tdee,
        "activity_factor": activity_factor,
        "goal_type": goal_type,
        "calorie_adjustment": calorie_adjustment,
        "safety_adjusted_goal": is_unsafe,
        "target_calories": target_calories,
        "target_protein_g": target_protein_g,
        "target_carbs_g": target_carbs_g,
        "target_fats_g": target_fats_g
    }
    
    # 5. Format ALL recipes with PORTION MULTIPLIERS (let LLM decide)
    def format_recipe_with_portions(recipe):
        base_macros = recipe.get('macros', {})
        base_cal = base_macros.get('calories', 0)
        base_pro = base_macros.get('protein_g', 0)
        base_carbs = base_macros.get('carbs_g', 0)
        base_fats = base_macros.get('fats_g', 0)
        
        return {
            "recipe_id": recipe.get('id', ''),
            "recipe_name": recipe.get('name', ''),
            "ready_in_minutes": recipe.get('ready_in_minutes'),
            "diet_tags": recipe.get('diets', []),
            "base_calories": base_cal,
            "base_protein_g": round(base_pro, 1),
            "base_carbs_g": round(base_carbs, 1),
            "base_fats_g": round(base_fats, 1),
            "portion_options": [
                {"multiplier": 0.5, "calories": int(base_cal * 0.5), "protein_g": round(base_pro * 0.5, 1), "carbs_g": round(base_carbs * 0.5, 1), "fats_g": round(base_fats * 0.5, 1)},
                {"multiplier": 1.0, "calories": base_cal, "protein_g": round(base_pro, 1), "carbs_g": round(base_carbs, 1), "fats_g": round(base_fats, 1)},
                {"multiplier": 1.5, "calories": int(base_cal * 1.5), "protein_g": round(base_pro * 1.5, 1), "carbs_g": round(base_carbs * 1.5, 1), "fats_g": round(base_fats * 1.5, 1)},
                {"multiplier": 2.0, "calories": int(base_cal * 2.0), "protein_g": round(base_pro * 2.0, 1), "carbs_g": round(base_carbs * 2.0, 1), "fats_g": round(base_fats * 2.0, 1)}
            ],
            "ingredients": recipe.get('ingredients', ''),
            "instructions": recipe.get('instructions', '')
        }
    
    # Categorize by calorie density for snacks vs meals
    snack_candidates = [r for r in recipes if r.get('macros', {}).get('calories', 0) < 400]
    meal_candidates = [r for r in recipes if r.get('macros', {}).get('calories', 0) >= 200]
    
    all_meal_options = [format_recipe_with_portions(r) for r in meal_candidates[:25]]
    all_snack_options = [format_recipe_with_portions(r) for r in snack_candidates[:10]]
    
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
    
    workout_options = [format_exercise(ex) for ex in exercises[:12]]
    
    # 7. Ask LLM to build complete plan (LLM focuses on selection + personalization, NOT calculation)
    llm_prompt = f"""You are a SENIOR NUTRITIONIST and fitness expert. Build a complete 7-day meal and workout plan.

USER PROFILE:
- {request.user_profile.age}y {request.user_profile.sex}, {request.user_profile.weight_kg}kg, {request.user_profile.height_cm}cm, BMI: {bmi:.1f}
- Activity Level: {request.user_profile.activity_level}
- BMR: {bmr} kcal | TDEE: {tdee} kcal
- Goal: {request.query}

DAILY NUTRITIONAL TARGETS (CRITICAL - MUST BE MET):
- Calories: {target_calories} kcal (TDEE {calorie_adjustment:+.0%})
- Protein: {target_protein_g}g ({protein_multiplier}g/kg - essential for {goal_type})
- Carbs: {target_carbs_g}g
- Fats: {target_fats_g}g

AVAILABLE RESOURCES:
- {len(all_meal_options)} meal options (each with 4 portion sizes: 0.5x, 1x, 1.5x, 2x)
- {len(all_snack_options)} snack options (each with 4 portion sizes: 0.5x, 1x, 1.5x, 2x)
- {len(workout_options)} exercises

STRICT RULES - YOU MUST FOLLOW:
1. **ALWAYS respond in ENGLISH** (all text, tips, recommendations)
2. **ONLY use recipe_indices from the provided databases** (0-{len(all_meal_options)-1} for meals, 0-{len(all_snack_options)-1} for snacks)
3. **ONLY use exercise_indices from the provided database** (0-{len(workout_options)-1})
4. **DO NOT invent meals, recipes, exercises, calories, or macros**
5. **Use portion_multipliers (0.5, 1.0, 1.5, 2.0) to hit calorie targets precisely**
6. **Include 2-3 snacks per day** to meet calorie goals
7. **Prioritize high-protein recipes** for muscle-related goals
8. **Calculate daily_totals by summing the actual recipe macros × portions**

MEAL DISTRIBUTION STRATEGY:
- Breakfast: 25-30% of daily calories
- Morning Snack: 5-10%
- Lunch: 30-35%
- Afternoon Snack: 5-10%
- Dinner: 25-30%
- Evening Snack (optional): 5%

WORKOUT FREQUENCY:
- weight_loss: 4-5 days/week
- muscle_gain: 4 days/week
- maintenance: 3 days/week
- recomp: 5 days/week

Return ONLY this exact JSON structure (NO MARKDOWN, NO EXTRA TEXT):
{{
  "plan_summary": {{
    "title": "Clear English title reflecting {goal_type}",
    "goal_detected": "{goal_type}",
    "short_summary": "1-2 sentences explaining the nutritional strategy",
    "focus": "Main nutritional focus based on BMR/TDEE calculations",
    "difficulty_level": "Beginner/Intermediate/Advanced"
  }},
  "weekly_calendar": [
    {{
      "day": "Monday",
      "meals": [
        {{"meal_type": "Breakfast", "recipe_indices": [0], "portion_multipliers": [1.5]}},
        {{"meal_type": "Morning Snack", "recipe_indices": [0], "portion_multipliers": [1.0]}},
        {{"meal_type": "Lunch", "recipe_indices": [5], "portion_multipliers": [1.0]}},
        {{"meal_type": "Afternoon Snack", "recipe_indices": [2], "portion_multipliers": [1.0]}},
        {{"meal_type": "Dinner", "recipe_indices": [12], "portion_multipliers": [1.5]}}
      ],
      "daily_totals": {{"calories": 0, "protein_g": 0, "carbs_g": 0, "fats_g": 0}},
      "workout": {{"exercise_indices": [0,1,2,3], "focus": "Legs", "duration_min": 45}},
      "notes": "Professional tip for the day"
    }}
  ],
  "ai_recommendations": {{
    "main_tip": "Key nutritional advice based on BMR/TDEE science",
    "personalized_notes": ["Note about their activity level and goal", "Hydration and recovery tip"],
    "nutrition_tips": ["Macro distribution strategy", "Meal timing for {goal_type}"],
    "workout_tips": ["Training frequency recommendation", "Recovery and rest importance"],
    "safety_notes": ["Important safety consideration for this goal type"]
  }}
}}

CRITICAL: Python will validate your response. DO NOT invent calories or macros. Use ONLY the provided recipe indices."""

    # Send to LLM with context about all options
    context_for_llm = {
        "meal_options": all_meal_options,
        "snack_options": all_snack_options,
        "workout_options": workout_options
    }
    workout_summary = [{'index': i, 'name': ex['name'], 'target': ex['target_muscle'], 'equipment': ex['equipment']} for i, ex in enumerate(workout_options)]
    
    full_prompt = f"""{llm_prompt}

MEAL OPTIONS DATABASE (index 0-{len(all_meal_options)-1}):
{json.dumps(all_meal_options[:15], indent=2)}
... ({len(all_meal_options)} total meal options available)

SNACK OPTIONS DATABASE (index 0-{len(all_snack_options)-1}):
{json.dumps(all_snack_options[:8], indent=2)}
... ({len(all_snack_options)} total snack options available)

WORKOUT OPTIONS DATABASE (index 0-{len(workout_options)-1}):
{json.dumps(workout_summary, indent=2)}"""

    try:
        chat_completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": full_prompt}],
            temperature=0.2,  # Lower temperature for consistency
            max_tokens=4000,
            response_format={"type": "json_object"}
        )
        response_text = chat_completion.choices[0].message.content
        llm_data = json.loads(response_text)
        print(f"✓ LLM responded: {len(response_text)} chars")
    except Exception as e:
        print(f"✗ LLM error: {e}")
        raise HTTPException(status_code=500, detail=f"OpenAI error: {str(e)}")
    
    # 8. VALIDATE nutrition plan - Python recalculates and validates macros
    weekly_calendar = llm_data.get('weekly_calendar', [])
    
    validation_result = validate_nutrition_plan(
        weekly_calendar,
        target_calories,
        target_protein_g,
        all_meal_options,
        all_snack_options
    )
    
    # Use Python-validated macros (not LLM-reported values)
    recalc_macros = validation_result['recalculated_macros']
    avg_daily_cal = recalc_macros['avg_daily_calories']
    avg_daily_pro = recalc_macros['avg_daily_protein_g']
    avg_daily_carbs = recalc_macros['avg_daily_carbs_g']
    avg_daily_fats = recalc_macros['avg_daily_fats_g']
    
    print(f"\n✅ Validation: Calories {'✓' if validation_result['calories_within_range'] else '✗'} | Protein {'✓' if validation_result['protein_sufficient'] else '✗'}")
    if validation_result['warnings']:
        print(f"   ⚠️ {len(validation_result['warnings'])} validation warnings")
    
    nutrition_summary = {
        "total_daily_calories_avg": avg_daily_cal,
        "total_daily_protein_g_avg": avg_daily_pro,
        "total_daily_carbs_g_avg": avg_daily_carbs,
        "total_daily_fats_g_avg": avg_daily_fats,
        "calculation_method": "python_validated"
    }
    
    macro_bars = [
        {"label": "Calories", "value": avg_daily_cal, "unit": "kcal", "target": target_calories, "percentage": int((avg_daily_cal / target_calories) * 100) if target_calories > 0 else 0},
        {"label": "Protein", "value": avg_daily_pro, "unit": "g", "target": target_protein_g, "percentage": int((avg_daily_pro / target_protein_g) * 100) if target_protein_g > 0 else 0},
        {"label": "Carbs", "value": avg_daily_carbs, "unit": "g", "target": target_carbs_g, "percentage": int((avg_daily_carbs / target_carbs_g) * 100) if target_carbs_g > 0 else 0},
        {"label": "Fats", "value": avg_daily_fats, "unit": "g", "target": target_fats_g, "percentage": int((avg_daily_fats / target_fats_g) * 100) if target_fats_g > 0 else 0}
    ]
    
    # 9. Build complete response with validation results
    ai_recommendations = llm_data.get('ai_recommendations', {})
    
    # Add safety warnings to AI recommendations if present
    if safety_warnings:
        existing_safety = ai_recommendations.get('safety_notes', [])
        ai_recommendations['safety_notes'] = safety_warnings + existing_safety
    complete_plan = {
        "plan_summary": llm_data.get('plan_summary', {}),
        "user_profile_summary": user_profile_summary,
        "nutrition_summary": nutrition_summary,
        "nutrition_validation": validation_result,
        "macro_bars": macro_bars,
        "meal_options": all_meal_options,
        "snack_options": all_snack_options,
        "workout_options": workout_options,
        "weekly_calendar": weekly_calendar,
        "ai_recommendations": ai_recommendations,
        "retrieved_data_summary": {
            "recipes_retrieved": len(recipes),
            "meal_options_available": len(all_meal_options),
            "snack_options_available": len(all_snack_options),
            "exercises_used": len(exercises),
            "source": "Elasticsearch k-NN (zero-macro filtered)",
            "validation_method": "python_recalculated"
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
        "name": "Fitness RAG API v3",
        "version": "3.0.0",
        "architecture": "Professional Nutrition-Tech: BMR/TDEE + Python validation + LLM personalization",
        "features": [
            "BMR calculation (Mifflin-St Jeor equation)",
            "TDEE calculation with activity levels",
            "Safety checks for extreme goals",
            "Python-validated macronutrient calculations",
            "Zero-macro recipe filtering",
            "Portion multipliers (0.5x, 1x, 1.5x, 2x)",
            "Lower LLM temperature for consistency (0.2)"
        ],
        "endpoints": {
            "health": "/health",
            "recommend": "/api/recommend (POST)",
            "docs": "/docs"
        }
    }
