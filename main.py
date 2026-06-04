#!/usr/bin/env python3
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

es_client = Elasticsearch(
    os.getenv('ELASTICSEARCH_URL'),
    api_key=os.getenv('ELASTICSEARCH_API_KEY')
)
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

print("Loading embedding model...")
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
print("Model loaded successfully.")

app = FastAPI(title="Fitness RAG API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class UserProfile(BaseModel):
    age: int
    sex: str
    weight_kg: float
    height_cm: float
    activity_level: str = "moderately_active"

class QueryRequest(BaseModel):
    query: str
    user_profile: UserProfile

class RecommendationResponse(BaseModel):
    response: str
    plan: dict
    raw_data: dict

def calculate_bmr(weight_kg, height_cm, age, sex):
    sex_normalized = sex.lower()
    if sex_normalized in ['male', 'hombre', 'm', 'man']:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    return round(bmr, 2)

def get_activity_factor(activity_level):
    activity_factors = {
        "sedentary": 1.2, "lightly_active": 1.375,
        "moderately_active": 1.55, "very_active": 1.725, "extra_active": 1.9
    }
    return activity_factors.get(activity_level.lower(), 1.55)

def calculate_tdee(bmr, activity_factor):
    return int(bmr * activity_factor)

def classify_goal(query):
    goal_lower = query.lower()
    has_weight_loss = any(w in goal_lower for w in ['perder','bajar','lose','weight loss','adelgazar','reducir','grasa','fat','cut','deficit'])
    has_muscle_gain = any(w in goal_lower for w in ['ganar','aumentar','bulk','masa','gain','muscle','músculo','muscular','hypertrophy'])
    if has_weight_loss and has_muscle_gain:
        return ('recomp', -0.10, 2.2)
    elif has_weight_loss:
        return ('weight_loss', -0.20, 2.0)
    elif has_muscle_gain:
        return ('muscle_gain', 0.15, 1.8)
    elif any(w in goal_lower for w in ['mantener','maintain','tonificar','tone']):
        return ('maintenance', 0.0, 1.6)
    else:
        return ('maintenance', 0.0, 1.6)

def apply_goal_adjustment(tdee, calorie_adjustment):
    return int(tdee * (1 + calorie_adjustment))

def detect_unsafe_goal(query, target_calories, sex, tdee):
    warnings = []
    is_unsafe = False
    adjusted_calories = target_calories
    sex_normalized = sex.lower()
    min_calories = 1500 if sex_normalized in ['male','hombre','m','man'] else 1200
    query_lower = query.lower()
    extreme_phrases = ['lose 10','lose 20','perder 10','perder 20','in 2 weeks','en 2 semanas','in 1 week','en 1 semana','crash','extreme','fast','rapid','rapido','extremo','starvation','starve','purge','hambre']
    if any(p in query_lower for p in extreme_phrases):
        is_unsafe = True
        warnings.append("Your goal may be too aggressive. Safe weight loss is 0.5-1kg per week.")
    if target_calories < min_calories:
        is_unsafe = True
        adjusted_calories = min_calories
        warnings.append(f"Target calories ({target_calories} kcal) adjusted to safe minimum ({min_calories} kcal).")
    deficit_pct = (tdee - target_calories) / tdee if tdee > 0 else 0
    if deficit_pct > 0.25:
        is_unsafe = True
        adjusted_calories = max(int(tdee * 0.75), min_calories)
        warnings.append(f"Calorie deficit too large ({int(deficit_pct*100)}%). Adjusted to 25% maximum deficit.")
    surplus_pct = (target_calories - tdee) / tdee if tdee > 0 else 0
    if surplus_pct > 0.20:
        is_unsafe = True
        adjusted_calories = int(tdee * 1.20)
        warnings.append(f"Calorie surplus too large ({int(surplus_pct*100)}%). Adjusted to 20% maximum.")
    return (is_unsafe, adjusted_calories, warnings)

def validate_nutrition_plan(daily_totals, target_calories, target_protein_g, all_meal_options, all_snack_options):
    # BUG #2-A: ahora devuelve recalculated_days (per-day) además del promedio.
    # BUG #2-B: is_snack usa `in` para capturar cualquier variante del LLM que contenga "snack".
    warnings = []
    calories_within_range = True
    protein_sufficient = True
    recalculated_days = []

    for day in daily_totals:
        day_cal = 0.0; day_pro = 0.0; day_carbs = 0.0; day_fats = 0.0
        for meal in day.get('meals', []):
            recipe_indices      = meal.get('recipe_indices', [])
            portion_multipliers = meal.get('portion_multipliers', [1.0] * len(recipe_indices))
            # BUG #2-B: 'snack' in meal_type captura "Snack 1", "Evening Snack", "Snack (AM)", etc.
            is_snack    = 'snack' in meal.get('meal_type', '').lower()
            recipe_list = all_snack_options if is_snack else all_meal_options

            for idx, multiplier in zip(recipe_indices, portion_multipliers):
                if not (0 <= idx < len(recipe_list)):
                    warnings.append(
                        f"Invalid {'snack' if is_snack else 'meal'} index {idx} "
                        f"(valid: 0–{len(recipe_list)-1}). Skipped."
                    )
                    continue
                recipe = recipe_list[idx]
                day_cal   += recipe['base_calories']  * multiplier
                day_pro   += recipe['base_protein_g'] * multiplier
                day_carbs += recipe['base_carbs_g']   * multiplier
                day_fats  += recipe['base_fats_g']    * multiplier

        recalculated_days.append({
            'calories':  int(day_cal),
            'protein_g': round(day_pro, 1),
            'carbs_g':   round(day_carbs, 1),
            'fats_g':    round(day_fats, 1),
        })

    if recalculated_days:
        n = len(recalculated_days)
        avg_cal   = int(sum(d['calories']  for d in recalculated_days) / n)
        avg_pro   = round(sum(d['protein_g'] for d in recalculated_days) / n, 1)
        avg_carbs = round(sum(d['carbs_g']   for d in recalculated_days) / n, 1)
        avg_fats  = round(sum(d['fats_g']    for d in recalculated_days) / n, 1)
    else:
        avg_cal = avg_pro = avg_carbs = avg_fats = 0
        warnings.append("No meal data to validate")

    calorie_tolerance = target_calories * 0.05
    if abs(avg_cal - target_calories) > calorie_tolerance:
        calories_within_range = False
        diff_pct = int(((avg_cal - target_calories) / target_calories) * 100)
        warnings.append(f"Calories off target: {avg_cal} kcal vs {target_calories} kcal ({diff_pct:+d}%).")
    if avg_pro < target_protein_g * 0.90:
        protein_sufficient = False
        shortfall_pct = int(((avg_pro - target_protein_g) / target_protein_g) * 100)
        warnings.append(f"Protein below target: {avg_pro}g vs {target_protein_g}g ({shortfall_pct:+d}%).")

    return {
        "calories_within_range": calories_within_range,
        "protein_sufficient":    protein_sufficient,
        "warnings":              warnings,
        "recalculated_days":     recalculated_days,   # ← NUEVO: per-day para inyectar en weekly_calendar
        "recalculated_macros": {
            "avg_daily_calories":  avg_cal,
            "avg_daily_protein_g": avg_pro,
            "avg_daily_carbs_g":   avg_carbs,
            "avg_daily_fats_g":    avg_fats,
        },
    }

def search_elasticsearch(index_name, query_vector, k=3, filter_zero_macros=False):
    # FIX #4: _source: True — los documentos se indexan como objetos, no como search_context string.
    # Si tus docs aún tienen search_context, ver nota en patches_rag_api.py sobre el indexing script.
    search_query = {
        "knn": {"field": "embedding", "query_vector": query_vector, "k": k * 4, "num_candidates": 150},
        "_source": True,
    }
    try:
        response = es_client.search(index=index_name, body=search_query)
    except Exception as e:
        print(f"[ES ERROR] search on '{index_name}' failed: {e}")
        return []

    results = []
    for hit in response["hits"]["hits"]:
        try:
            doc = dict(hit["_source"])
            doc["_score"] = hit["_score"]
            results.append(doc)
        except (KeyError, TypeError) as e:
            print(f"[ES WARN] Could not read hit from '{index_name}': {e}")
            continue

    if filter_zero_macros and index_name == "recipes":
        before = len(results)
        results = [r for r in results if r.get("macros", {}).get("calories", 0) > 0]
        print(f"   [filter_zero_macros] {index_name}: {before} → {len(results)} docs")

    if index_name == "recipes":
        fatsecret = [r for r in results if r.get("id", "").startswith("rec_fs_")]
        others    = [r for r in results if not r.get("id", "").startswith("rec_fs_")]
        results   = fatsecret + others

    return results[:k]

@app.get("/health")
def health_check():
    return {"status": "active", "elasticsearch": "connected" if es_client.ping() else "disconnected"}

@app.post("/api/recommend", response_model=RecommendationResponse)
def get_recommendation(request: QueryRequest):
    try:
        query_vector = model.encode(request.query).tolist()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating embedding: {str(e)}")
    exercises = search_elasticsearch("exercises", query_vector, k=12)
    main_recipes = search_elasticsearch("recipes", query_vector, k=30, filter_zero_macros=True)
    # FIX #5: snack vector incorpora el objetivo del usuario en lugar de un hardcode genérico
    _snack_hints = {
        "weight_loss":  "low calorie snacks high fiber fruits vegetables",
        "muscle_gain":  "high protein snacks greek yogurt cottage cheese protein bars",
        "recomp":       "high protein low calorie snacks lean foods",
        "maintenance":  "balanced snacks nuts fruits whole grains",
    }
    _early_goal_type, _, _ = classify_goal(request.query)
    snack_query = f"{request.query} {_snack_hints.get(_early_goal_type, 'healthy balanced snacks')}"
    snack_query_vector = model.encode(snack_query).tolist()
    snack_recipes = search_elasticsearch("recipes", snack_query_vector, k=15, filter_zero_macros=True)
    all_recipes_dict = {r['id']: r for r in main_recipes + snack_recipes}
    recipes = list(all_recipes_dict.values())
    bmr = calculate_bmr(request.user_profile.weight_kg, request.user_profile.height_cm, request.user_profile.age, request.user_profile.sex)
    activity_factor = get_activity_factor(request.user_profile.activity_level)
    tdee = calculate_tdee(bmr, activity_factor)
    goal_type, calorie_adjustment, protein_multiplier = classify_goal(request.query)
    target_calories_initial = apply_goal_adjustment(tdee, calorie_adjustment)
    is_unsafe, target_calories, safety_warnings = detect_unsafe_goal(request.query, target_calories_initial, request.user_profile.sex, tdee)
    target_protein_g = int(request.user_profile.weight_kg * protein_multiplier)
    target_fats_g = int((target_calories * 0.275) / 9)
    protein_calories = target_protein_g * 4
    fat_calories = target_fats_g * 9
    target_carbs_g = int((target_calories - protein_calories - fat_calories) / 4)
    bmi = request.user_profile.weight_kg / ((request.user_profile.height_cm / 100) ** 2)

    def format_recipe_with_portions(recipe):
        base_macros = recipe.get('macros', {})
        base_cal = base_macros.get('calories', 0); base_pro = base_macros.get('protein_g', 0)
        base_carbs = base_macros.get('carbs_g', 0); base_fats = base_macros.get('fats_g', 0)
        return {"recipe_id": recipe.get('id',''), "recipe_name": recipe.get('name',''), "ready_in_minutes": recipe.get('ready_in_minutes'), "diet_tags": recipe.get('diets',[]), "base_calories": base_cal, "base_protein_g": round(base_pro,1), "base_carbs_g": round(base_carbs,1), "base_fats_g": round(base_fats,1),
                "portion_options": [{"multiplier": 0.5, "calories": int(base_cal*0.5), "protein_g": round(base_pro*0.5,1), "carbs_g": round(base_carbs*0.5,1), "fats_g": round(base_fats*0.5,1)}, {"multiplier": 1.0, "calories": base_cal, "protein_g": round(base_pro,1), "carbs_g": round(base_carbs,1), "fats_g": round(base_fats,1)}, {"multiplier": 1.5, "calories": int(base_cal*1.5), "protein_g": round(base_pro*1.5,1), "carbs_g": round(base_carbs*1.5,1), "fats_g": round(base_fats*1.5,1)}, {"multiplier": 2.0, "calories": int(base_cal*2.0), "protein_g": round(base_pro*2.0,1), "carbs_g": round(base_carbs*2.0,1), "fats_g": round(base_fats*2.0,1)}],
                "ingredients": recipe.get('ingredients',''), "instructions": recipe.get('instructions','')}

    snack_candidates = [r for r in recipes if r.get('macros',{}).get('calories',0) < 400]
    meal_candidates  = [r for r in recipes if r.get('macros',{}).get('calories',0) >= 200]
    # BUG #1: los límites declarados al LLM = los docs que realmente ve en el prompt.
    # 15 meals + 8 snacks son suficientes para 7 días con variedad sin sobrecargar el contexto.
    MAX_MEAL_OPTIONS  = 15
    MAX_SNACK_OPTIONS = 8
    all_meal_options  = [format_recipe_with_portions(r) for r in meal_candidates[:MAX_MEAL_OPTIONS]]
    all_snack_options = [format_recipe_with_portions(r) for r in snack_candidates[:MAX_SNACK_OPTIONS]]

    def format_exercise(exercise):
        return {"exercise_id": exercise.get('id',''), "name": exercise.get('name',''), "target_muscle": exercise.get('target_muscle',''), "equipment": exercise.get('equipment',''), "estimated_met": exercise.get('estimated_met'), "instructions": exercise.get('instructions','')}

    workout_options = [format_exercise(ex) for ex in exercises[:12]]
    workout_summary = [{'index': i, 'name': ex['name'], 'target': ex['target_muscle'], 'equipment': ex['equipment']} for i, ex in enumerate(workout_options)]

    llm_prompt = f"""You are a SENIOR NUTRITIONIST and fitness expert. Build a complete 7-day meal and workout plan.

USER PROFILE: {request.user_profile.age}y {request.user_profile.sex}, {request.user_profile.weight_kg}kg, {request.user_profile.height_cm}cm, BMI: {bmi:.1f}
Activity Level: {request.user_profile.activity_level}
User Goal: {request.query}

AVAILABLE RESOURCES:
- {len(all_meal_options)} meal options with portion sizes (0.5x, 1x, 1.5x, 2x)
- {len(all_snack_options)} snack options with portion sizes (0.5x, 1x, 1.5x, 2x)
- {len(workout_options)} exercises

STRICT RULES:
1. ALWAYS respond in ENGLISH
2. ONLY use recipe_indices 0-{len(all_meal_options)-1} for meals, 0-{len(all_snack_options)-1} for snacks
3. ONLY use exercise_indices 0-{len(workout_options)-1}
4. DO NOT invent meals, recipes, exercises, or nutritional values
5. Use portion_multipliers (0.5, 1.0, 1.5, 2.0) strategically
6. Include 2-3 snacks per day for balanced nutrition
7. Prioritize high-protein recipes for muscle-related goals
8. DO NOT include daily_totals in your response. Python calculates them.
9. DO NOT mention calorie targets or macro targets anywhere in your text

Return ONLY this exact JSON (ALL IN ENGLISH):
{{
  "plan_summary": {{
    "title": "Descriptive plan title in English",
    "goal_detected": "descriptive goal phrase",
    "short_summary": "Brief explanation of the nutritional strategy",
    "focus": "Main nutritional focus",
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
      "workout": {{"exercise_indices": [0,1,2,3], "focus": "Legs", "duration_min": 45}},
      "notes": "Brief tip in English without mentioning specific calorie or macro numbers"
    }}
  ],
  "ai_recommendations": {{
    "main_tip": "Key nutritional advice in English (no numbers)",
    "personalized_notes": ["Observation about user's profile", "General wellness tip"],
    "nutrition_tips": ["Meal timing tip", "Food quality tip"],
    "workout_tips": ["Training frequency advice", "Recovery tip"],
    "safety_notes": ["Safety consideration"]
  }}
}}"""

    full_prompt = f"""{llm_prompt}
MEAL OPTIONS DATABASE (index 0-{len(all_meal_options)-1}):
{json.dumps(all_meal_options, indent=2)}

SNACK OPTIONS DATABASE (index 0-{len(all_snack_options)-1}):
{json.dumps(all_snack_options, indent=2)}
WORKOUT OPTIONS DATABASE (index 0-{len(workout_options)-1}):
{json.dumps(workout_summary, indent=2)}"""

    try:
        chat_completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": full_prompt}],
            temperature=0.2, max_tokens=4000,
            response_format={"type": "json_object"}
        )
        response_text = chat_completion.choices[0].message.content
        llm_data = json.loads(response_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI error: {str(e)}")

    weekly_calendar   = llm_data.get('weekly_calendar', [])
    validation_result = validate_nutrition_plan(
        weekly_calendar, target_calories, target_protein_g, all_meal_options, all_snack_options
    )

    # BUG #2-B: Python inyecta daily_totals como única fuente de verdad.
    # El LLM ya no los reporta (los eliminamos del schema del prompt).
    # El frontend puede renderizarlos directamente desde weekly_calendar sin lógica adicional.
    recalculated_days = validation_result.get('recalculated_days', [])
    for i, day in enumerate(weekly_calendar):
        day['daily_totals'] = (
            recalculated_days[i]
            if i < len(recalculated_days)
            else {'calories': 0, 'protein_g': 0.0, 'carbs_g': 0.0, 'fats_g': 0.0}
        )

    ai_recommendations = llm_data.get('ai_recommendations', {})
    if safety_warnings:
        existing = ai_recommendations.get('safety_notes', [])
        ai_recommendations['safety_notes'] = safety_warnings + existing

    # Crear nutrition_summary desde los datos validados (SIN mostrar targets)
    recalc_macros = validation_result['recalculated_macros']
    nutrition_summary = {
        "avg_daily_calories": recalc_macros['avg_daily_calories'],
        "avg_daily_protein_g": recalc_macros['avg_daily_protein_g'],
        "avg_daily_carbs_g": recalc_macros['avg_daily_carbs_g'],
        "avg_daily_fats_g": recalc_macros['avg_daily_fats_g']
    }
    
    # Crear macro_bars SIN targets ni porcentajes
    macro_bars = [
        {
            "label": "Calories",
            "value": recalc_macros['avg_daily_calories'],
            "unit": "kcal"
        },
        {
            "label": "Protein",
            "value": recalc_macros['avg_daily_protein_g'],
            "unit": "g"
        },
        {
            "label": "Carbs",
            "value": recalc_macros['avg_daily_carbs_g'],
            "unit": "g"
        },
        {
            "label": "Fats",
            "value": recalc_macros['avg_daily_fats_g'],
            "unit": "g"
        }
    ]

    complete_plan = {
        "plan_summary":        llm_data.get('plan_summary', {}),
        "user_profile_summary": {
            "age": request.user_profile.age,
            "sex": request.user_profile.sex,
            "weight_kg": request.user_profile.weight_kg,
            "height_cm": request.user_profile.height_cm,
            "bmi": round(bmi, 2),
            "activity_level": request.user_profile.activity_level
        },
        "nutrition_summary":   nutrition_summary,
        "macro_bars":          macro_bars,
        "meal_options":        all_meal_options,
        "snack_options":       all_snack_options,
        "workout_options":     workout_options,
        "weekly_calendar":     weekly_calendar,
        "ai_recommendations":  ai_recommendations
    }
    return {
        "response": json.dumps(complete_plan, ensure_ascii=False),
        "plan":     complete_plan,
        "raw_data": {"exercises": exercises, "recipes": recipes},
    }