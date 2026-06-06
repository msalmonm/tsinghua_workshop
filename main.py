#!/usr/bin/env python3
import os
import re
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
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

app = FastAPI(title="Fitness RAG API", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================================
# NUTRITION & SAFETY THRESHOLDS
# Sources (2025-2030 Dietary Guidelines for Americans, ISSN position
# stand, Institute of Medicine AMDR). All values reviewed against
# current professional references:
#   - Protein: 1.2-1.6 g/kg general; 1.6-2.4 g/kg for muscle building /
#     cutting (ISSN). Hard cap 2.4 g/kg.
#   - Fat: minimum 0.5 g/kg AND >= 20% of calories; cap 35% of calories.
#   - Carbohydrate AMDR: 45-65% of calories (lower allowed for high
#     protein / low carb goals, but never negative).
#   - Calorie deficit: moderate 250-500 kcal; hard cap 25% below TDEE.
#   - Calorie surplus: hard cap 20% above TDEE.
#   - Minimum daily calories: 1500 (male) / 1200 (female).
#   - Activity multipliers: standard Mifflin-St Jeor PAL factors.
#   - Macro tolerance: calories +/-10%, protein >= 90% of target.
#   - Weekly consistency: max-min daily spread < 15% for each macro.
# =====================================================================
NUTRITION = {
    "min_calories_male": 1500,
    "min_calories_female": 1200,
    "protein_g_per_kg": {
        "weight_loss": 1.8,
        "muscle_gain": 1.8,
        "recomp": 2.0,
        "maintenance": 1.4,
    },
    "protein_g_per_kg_floor": 1.2,
    "protein_g_per_kg_cap": 2.4,
    "fat_g_per_kg_min": 0.5,
    "fat_pct_min": 0.20,
    "fat_pct_max": 0.35,
    "carb_pct_min": 0.45,
    "carb_pct_max": 0.65,
    "max_deficit_pct": 0.25,
    "max_surplus_pct": 0.20,
    "calorie_tolerance_pct": 0.10,
    "protein_sufficiency_pct": 0.90,
    "weekly_spread_max_pct": 0.15,
}

ACTIVITY_FACTORS = {
    "sedentary": 1.2,
    "lightly_active": 1.375,
    "moderately_active": 1.55,
    "very_active": 1.725,
    "extremely_active": 1.9,
    "extra_active": 1.9,
    "athlete": 1.9,
}

# Map a requested body part to the exercise DB `target_muscle` values
# (yuhonas free-exercise-db primary muscles).
BODY_PART_KEYWORDS = {
    "chest": ["chest", "pec", "bench press", "pecho"],
    "shoulders": ["shoulder", "delt", "overhead press", "hombro"],
    "back": ["back", "lat", "row", "pull-up", "pullup", "pulldown", "espalda", "dorsal"],
    "legs": ["leg", "quad", "squat", "hamstring", "glute", "calf", "calves", "lunge", "pierna", "cuadricep"],
    "arms": ["arm", "bicep", "tricep", "curl", "brazo"],
    "core": ["core", "abs", "abdominal", "plank", "oblique", "abdomen"],
    "cardio": ["cardio", "endurance", "running", "hiit", "conditioning", "stamina", "aerobic"],
    "full_body": ["full body", "full-body", "total body", "whole body"],
}

BODY_PART_TO_MUSCLES = {
    "chest": ["chest"],
    "shoulders": ["shoulders"],
    "back": ["lats", "middle back", "lower back", "traps"],
    "legs": ["quadriceps", "hamstrings", "glutes", "calves", "adductors", "abductors"],
    "arms": ["biceps", "triceps", "forearms"],
    "core": ["abdominals"],
    "cardio": [],
    "full_body": [],
}

WORD_TO_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7,
}

BREAKFAST_KEYWORDS = [
    "egg", "omelet", "omelette", "pancake", "waffle", "oat", "oatmeal", "porridge",
    "cereal", "granola", "smoothie", "yogurt", "yoghurt", "toast", "bagel", "muffin",
    "bacon", "french toast", "crepe", "scramble", "breakfast",
]
SNACK_KEYWORDS = [
    "bar", "nuts", "fruit", "chips", "dip", "hummus", "cracker", "cookie",
    "popcorn", "trail mix", "smoothie", "yogurt", "yoghurt", "snack",
]


class UserProfile(BaseModel):
    age: int
    sex: str
    weight_kg: float
    height_cm: float
    activity_level: str = "moderately_active"

    @field_validator("age")
    @classmethod
    def validate_age(cls, v):
        if v <= 0:
            raise ValueError("Age must be a positive number.")
        if v < 13 or v > 100:
            raise ValueError("Age must be a realistic value between 13 and 100 years.")
        return v

    @field_validator("height_cm")
    @classmethod
    def validate_height(cls, v):
        if v <= 0:
            raise ValueError("Height must be a positive number.")
        if v < 90:
            raise ValueError(
                "Please enter your height in centimeters, for example 180 instead of 1.8."
            )
        if v > 250:
            raise ValueError("Height must be a realistic value in centimeters (90-250 cm).")
        return v

    @field_validator("weight_kg")
    @classmethod
    def validate_weight(cls, v):
        if v <= 0:
            raise ValueError("Weight must be a positive number.")
        if v < 25 or v > 400:
            raise ValueError("Weight must be a realistic value in kilograms (25-400 kg).")
        return v


class QueryRequest(BaseModel):
    query: str
    user_profile: UserProfile

    @field_validator("query")
    @classmethod
    def validate_query(cls, v):
        if not v or not v.strip():
            raise ValueError("Please describe what you want to achieve.")
        return v


class RecommendationResponse(BaseModel):
    response: str
    plan: dict
    raw_data: dict


# =====================================================================
# NUTRITION SCIENCE (deterministic, Python-owned)
# =====================================================================
def calculate_bmr(weight_kg, height_cm, age, sex):
    sex_normalized = sex.lower()
    if sex_normalized in ['male', 'hombre', 'm', 'man']:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    return round(bmr, 2)


def get_activity_factor(activity_level):
    return ACTIVITY_FACTORS.get(activity_level.lower(), 1.55)


def calculate_tdee(bmr, activity_factor):
    return int(bmr * activity_factor)


def classify_goal(query):
    goal_lower = query.lower()
    has_weight_loss = any(w in goal_lower for w in ['perder', 'bajar', 'lose', 'weight loss', 'adelgazar', 'reducir', 'grasa', 'fat loss', 'cut', 'deficit', 'lean', 'shred'])
    has_muscle_gain = any(w in goal_lower for w in ['ganar', 'aumentar', 'bulk', 'masa', 'gain', 'muscle', 'músculo', 'muscular', 'hypertrophy', 'strength', 'build'])
    if has_weight_loss and has_muscle_gain:
        return ('recomp', -0.10)
    elif has_weight_loss:
        return ('weight_loss', -0.20)
    elif has_muscle_gain:
        return ('muscle_gain', 0.15)
    elif any(w in goal_lower for w in ['mantener', 'maintain', 'tonificar', 'tone']):
        return ('maintenance', 0.0)
    else:
        return ('maintenance', 0.0)


def apply_goal_adjustment(tdee, calorie_adjustment):
    return int(tdee * (1 + calorie_adjustment))


def detect_unsafe_goal(query, target_calories, sex, tdee):
    warnings = []
    is_unsafe = False
    adjusted_calories = target_calories
    sex_normalized = sex.lower()
    min_calories = NUTRITION["min_calories_male"] if sex_normalized in ['male', 'hombre', 'm', 'man'] else NUTRITION["min_calories_female"]
    query_lower = query.lower()
    extreme_phrases = ['lose 10', 'lose 20', 'perder 10', 'perder 20', 'in 2 weeks', 'en 2 semanas', 'in 1 week', 'en 1 semana', 'crash', 'extreme', 'fastest', 'rapid', 'rapido', 'extremo', 'starvation', 'starve', 'purge', 'hambre']
    if any(p in query_lower for p in extreme_phrases):
        is_unsafe = True
        warnings.append("Your goal may be too aggressive. Safe weight loss is 0.5-1 kg per week.")
    if target_calories < min_calories:
        is_unsafe = True
        adjusted_calories = min_calories
        warnings.append(f"Target calories ({target_calories} kcal) adjusted to the safe minimum ({min_calories} kcal).")
    deficit_pct = (tdee - target_calories) / tdee if tdee > 0 else 0
    if deficit_pct > NUTRITION["max_deficit_pct"]:
        is_unsafe = True
        adjusted_calories = max(int(tdee * (1 - NUTRITION["max_deficit_pct"])), min_calories)
        warnings.append(f"Calorie deficit too large ({int(deficit_pct*100)}%). Adjusted to a {int(NUTRITION['max_deficit_pct']*100)}% maximum deficit.")
    surplus_pct = (target_calories - tdee) / tdee if tdee > 0 else 0
    if surplus_pct > NUTRITION["max_surplus_pct"]:
        is_unsafe = True
        adjusted_calories = int(tdee * (1 + NUTRITION["max_surplus_pct"]))
        warnings.append(f"Calorie surplus too large ({int(surplus_pct*100)}%). Adjusted to a {int(NUTRITION['max_surplus_pct']*100)}% maximum.")
    return (is_unsafe, adjusted_calories, warnings)


def compute_macro_targets(target_calories, weight_kg, goal_type):
    """Returns (protein_g, carbs_g, fats_g) using professional thresholds."""
    protein_per_kg = NUTRITION["protein_g_per_kg"].get(goal_type, 1.4)
    protein_per_kg = max(NUTRITION["protein_g_per_kg_floor"], min(protein_per_kg, NUTRITION["protein_g_per_kg_cap"]))
    target_protein_g = int(weight_kg * protein_per_kg)

    # Fat: at least 0.5 g/kg AND at least 20% of calories, capped at 35%.
    fat_floor_g = max(NUTRITION["fat_g_per_kg_min"] * weight_kg, (target_calories * NUTRITION["fat_pct_min"]) / 9)
    fat_cap_g = (target_calories * NUTRITION["fat_pct_max"]) / 9
    target_fats_g = int(min(fat_floor_g, fat_cap_g)) if fat_cap_g > 0 else int(fat_floor_g)

    protein_calories = target_protein_g * 4
    fat_calories = target_fats_g * 9
    target_carbs_g = int((target_calories - protein_calories - fat_calories) / 4)
    if target_carbs_g < 0:
        target_carbs_g = 0
    return target_protein_g, target_carbs_g, target_fats_g


# =====================================================================
# INTENT EXTRACTION (rule-based, runs before generation)
# =====================================================================
def extract_intent(query):
    q = (query or "").lower()

    # --- target body parts ---
    targets = []
    for part, kws in BODY_PART_KEYWORDS.items():
        if any(kw in q for kw in kws):
            targets.append(part)
    # If "full body" detected, it shouldn't override a specific part request
    specific = [t for t in targets if t not in ("full_body", "cardio")]
    target_body_parts = specific if specific else targets

    # --- number of days to generate ---
    num_days = None
    if re.search(r'\b(whole week|full week|weekly|7[\s-]?day|seven[\s-]?day|per week|a week|each day|every day|all week)\b', q):
        num_days = 7
    if num_days is None:
        m = re.search(r'(\d+)\s*[-\s]?\s*day', q)
        if m and not re.search(r'(\d+)\s*[-\s]?\s*day[s]?\s*(?:a|per)\s*week', q):
            num_days = max(1, min(7, int(m.group(1))))
    if num_days is None:
        for w, n in WORD_TO_NUM.items():
            if re.search(rf'\b{w}[\s-]?day', q):
                num_days = max(1, min(7, n))
                break
    if num_days is None and re.search(r'\b(one day|single day|just today|today only|for today)\b', q):
        num_days = 1
    if num_days is None:
        num_days = 7

    # --- training frequency (workout days per week) ---
    training_freq = None
    m = re.search(r'(\d+)\s*[-\s]?\s*(?:day|days|times|x|sessions?)\s*(?:a|per)?\s*week', q)
    if m:
        training_freq = int(m.group(1))
    if training_freq is None:
        m2 = re.search(r'(?:train|workout|work out|exercise|lift)\s*(\d+)\s*(?:day|days|times|x)', q)
        if m2:
            training_freq = int(m2.group(1))
    if training_freq is None:
        for w, n in WORD_TO_NUM.items():
            if re.search(rf'\b{w}\b\s*(?:day|days|times|x|sessions?)\s*(?:a|per)\s*week', q):
                training_freq = n
                break
    if training_freq is None and re.search(r'\b(daily|every day)\b', q):
        training_freq = 7
    if training_freq is None:
        training_freq = num_days if num_days <= 4 else 4
    training_freq = max(1, min(training_freq, num_days))

    # --- nutrition goal ---
    goal_type, _ = classify_goal(query)

    # --- dietary restrictions ---
    restrictions = []
    diet_map = {
        "vegetarian": ["vegetarian"],
        "vegan": ["vegan"],
        "gluten-free": ["gluten free", "gluten-free", "celiac"],
        "dairy-free": ["dairy free", "dairy-free", "lactose"],
        "keto": ["keto", "ketogenic", "low carb", "low-carb"],
        "pescatarian": ["pescatarian"],
        "halal": ["halal"],
        "nut-free": ["nut free", "nut-free", "peanut allergy", "nut allergy"],
    }
    for label, kws in diet_map.items():
        if any(kw in q for kw in kws):
            restrictions.append(label)

    # --- meal prep / repetitive style ---
    meal_prep = bool(re.search(r'\b(meal prep|meal-prep|same meals|repetitive|repeat the same|batch cook)\b', q))

    wants_weekly = num_days >= 7

    return {
        "fitness_goal": goal_type,
        "target_body_parts": target_body_parts,
        "training_frequency_per_week": training_freq,
        "nutrition_goal": goal_type,
        "dietary_restrictions": restrictions,
        "num_days": num_days,
        "wants_weekly_plan": wants_weekly,
        "meal_prep_style": meal_prep,
    }


# =====================================================================
# RETRIEVAL
# =====================================================================
def search_elasticsearch(index_name, query_vector, k=3, filter_zero_macros=False):
    search_query = {
        "knn": {"field": "embedding", "query_vector": query_vector, "k": k * 4, "num_candidates": 200},
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
        results = [r for r in results if r.get("macros", {}).get("calories", 0) > 0]

    if index_name == "recipes":
        fatsecret = [r for r in results if r.get("id", "").startswith("rec_fs_")]
        others = [r for r in results if not r.get("id", "").startswith("rec_fs_")]
        results = fatsecret + others

    return results[:k]


def diversify_by_name(recipes, limit):
    """Drop near-duplicate recipe names to increase retrieval diversity."""
    seen = set()
    out = []
    for r in recipes:
        name = (r.get("name") or "").lower()
        key = re.sub(r'[^a-z0-9]', '', name)[:22]
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(r)
        if len(out) >= limit:
            break
    return out


def select_exercises(pool, target_muscles, total=14, focus_ratio=0.55):
    """Body-part focus with full-body balance: the target gets ~55% of slots,
    the remainder keeps the routine balanced across other muscle groups."""
    if not pool:
        return []
    target_set = {m.lower() for m in target_muscles}
    if not target_set:
        # No specific focus: keep a balanced spread across muscle groups.
        balanced = []
        seen_muscles = {}
        for e in pool:
            m = (e.get("target_muscle") or "").lower()
            if seen_muscles.get(m, 0) < 3:
                balanced.append(e)
                seen_muscles[m] = seen_muscles.get(m, 0) + 1
            if len(balanced) >= total:
                break
        if len(balanced) < total:
            for e in pool:
                if e not in balanced:
                    balanced.append(e)
                if len(balanced) >= total:
                    break
        return balanced[:total]

    targeted = [e for e in pool if (e.get("target_muscle") or "").lower() in target_set]
    others = [e for e in pool if (e.get("target_muscle") or "").lower() not in target_set]
    n_target = max(1, int(round(total * focus_ratio)))
    selected = targeted[:n_target]
    for e in others:
        if len(selected) >= total:
            break
        selected.append(e)
    for e in targeted[n_target:]:
        if len(selected) >= total:
            break
        selected.append(e)
    return selected[:total]


def meal_hint_for(name, snack_friendly):
    n = (name or "").lower()
    if any(k in n for k in BREAKFAST_KEYWORDS):
        return "breakfast"
    if snack_friendly and any(k in n for k in SNACK_KEYWORDS):
        return "snack"
    return "main"


def format_recipe_with_portions(recipe):
    base_macros = recipe.get('macros', {})
    base_cal = base_macros.get('calories', 0)
    base_pro = base_macros.get('protein_g', 0)
    base_carbs = base_macros.get('carbs_g', 0)
    base_fats = base_macros.get('fats_g', 0)
    ingredients = recipe.get('ingredients', '') or ''
    ingredient_count = len([x for x in ingredients.split(',') if x.strip()]) if ingredients else 0
    prep = recipe.get('ready_in_minutes', 30) or 30
    # Snack-friendly hint: low calorie, few ingredients, quick to prepare.
    snack_friendly = bool(base_cal and base_cal < 320 and ingredient_count <= 7 and prep <= 20)
    return {
        "recipe_id": recipe.get('id', ''),
        "recipe_name": recipe.get('name', ''),
        "ready_in_minutes": prep,
        "ingredient_count": ingredient_count,
        "diet_tags": recipe.get('diets', []),
        "base_calories": base_cal,
        "base_protein_g": round(base_pro, 1),
        "base_carbs_g": round(base_carbs, 1),
        "base_fats_g": round(base_fats, 1),
        "snack_friendly": snack_friendly,
        "meal_hint": meal_hint_for(recipe.get('name', ''), snack_friendly),
        "portion_options": [
            {"multiplier": 0.5, "calories": int(base_cal * 0.5), "protein_g": round(base_pro * 0.5, 1), "carbs_g": round(base_carbs * 0.5, 1), "fats_g": round(base_fats * 0.5, 1)},
            {"multiplier": 1.0, "calories": base_cal, "protein_g": round(base_pro, 1), "carbs_g": round(base_carbs, 1), "fats_g": round(base_fats, 1)},
            {"multiplier": 1.5, "calories": int(base_cal * 1.5), "protein_g": round(base_pro * 1.5, 1), "carbs_g": round(base_carbs * 1.5, 1), "fats_g": round(base_fats * 1.5, 1)},
            {"multiplier": 2.0, "calories": int(base_cal * 2.0), "protein_g": round(base_pro * 2.0, 1), "carbs_g": round(base_carbs * 2.0, 1), "fats_g": round(base_fats * 2.0, 1)},
        ],
        "ingredients": ingredients,
        "instructions": recipe.get('instructions', ''),
        "recipe_image": recipe.get('recipe_image', ''),
        "recipe_url": recipe.get('recipe_url', ''),
    }


def format_exercise(exercise):
    return {
        "exercise_id": exercise.get('id', ''),
        "name": exercise.get('name', ''),
        "target_muscle": exercise.get('target_muscle', ''),
        "equipment": exercise.get('equipment', ''),
        "estimated_met": exercise.get('estimated_met'),
        "instructions": exercise.get('instructions', ''),
    }


# =====================================================================
# VALIDATION (single catalog source of truth + weekly balance)
# =====================================================================
def validate_nutrition_plan(daily_days, target_calories, target_protein_g, catalog):
    warnings = []
    calories_within_range = True
    protein_sufficient = True
    recalculated_days = []

    for day in daily_days:
        day_cal = day_pro = day_carbs = day_fats = 0.0
        seen_recipe_ids = []
        for meal in day.get('meals', []):
            recipe_indices = meal.get('recipe_indices', [])
            portion_multipliers = meal.get('portion_multipliers', [1.0] * len(recipe_indices))
            if len(portion_multipliers) < len(recipe_indices):
                portion_multipliers = portion_multipliers + [1.0] * (len(recipe_indices) - len(portion_multipliers))
            for idx, multiplier in zip(recipe_indices, portion_multipliers):
                if not (0 <= idx < len(catalog)):
                    warnings.append(f"Invalid recipe index {idx} (valid: 0-{len(catalog)-1}). Skipped.")
                    continue
                recipe = catalog[idx]
                rid = recipe.get('recipe_id')
                if rid in seen_recipe_ids:
                    warnings.append(f"Repeated recipe '{recipe.get('recipe_name')}' within {day.get('day','a day')}.")
                seen_recipe_ids.append(rid)
                day_cal += recipe['base_calories'] * multiplier
                day_pro += recipe['base_protein_g'] * multiplier
                day_carbs += recipe['base_carbs_g'] * multiplier
                day_fats += recipe['base_fats_g'] * multiplier
        recalculated_days.append({
            'calories': int(day_cal),
            'protein_g': round(day_pro, 1),
            'carbs_g': round(day_carbs, 1),
            'fats_g': round(day_fats, 1),
        })

    if recalculated_days:
        n = len(recalculated_days)
        avg_cal = int(sum(d['calories'] for d in recalculated_days) / n)
        avg_pro = round(sum(d['protein_g'] for d in recalculated_days) / n, 1)
        avg_carbs = round(sum(d['carbs_g'] for d in recalculated_days) / n, 1)
        avg_fats = round(sum(d['fats_g'] for d in recalculated_days) / n, 1)
    else:
        avg_cal = avg_pro = avg_carbs = avg_fats = 0
        warnings.append("No meal data to validate.")

    calorie_tolerance = target_calories * NUTRITION["calorie_tolerance_pct"]
    if abs(avg_cal - target_calories) > calorie_tolerance:
        calories_within_range = False
        diff_pct = int(((avg_cal - target_calories) / target_calories) * 100) if target_calories else 0
        warnings.append(f"Average calories off target: {avg_cal} kcal vs {target_calories} kcal ({diff_pct:+d}%).")
    if avg_pro < target_protein_g * NUTRITION["protein_sufficiency_pct"]:
        protein_sufficient = False
        shortfall_pct = int(((avg_pro - target_protein_g) / target_protein_g) * 100) if target_protein_g else 0
        warnings.append(f"Average protein below target: {avg_pro}g vs {target_protein_g}g ({shortfall_pct:+d}%).")

    # Weekly consistency: max-min spread per macro must stay < 15%.
    weekly_balance = {"balanced": True, "spreads": {}}
    if len(recalculated_days) > 1:
        for metric in ['calories', 'protein_g', 'carbs_g', 'fats_g']:
            values = [d[metric] for d in recalculated_days]
            hi, lo = max(values), min(values)
            spread = (hi - lo) / hi if hi > 0 else 0
            weekly_balance["spreads"][metric] = round(spread * 100, 1)
            if spread > NUTRITION["weekly_spread_max_pct"]:
                weekly_balance["balanced"] = False
                warnings.append(
                    f"Daily {metric.replace('_g','')} varies by {int(spread*100)}% across days "
                    f"(target < {int(NUTRITION['weekly_spread_max_pct']*100)}%)."
                )

    return {
        "calories_within_range": calories_within_range,
        "protein_sufficient": protein_sufficient,
        "warnings": warnings,
        "recalculated_days": recalculated_days,
        "weekly_balance": weekly_balance,
        "recalculated_macros": {
            "avg_daily_calories": avg_cal,
            "avg_daily_protein_g": avg_pro,
            "avg_daily_carbs_g": avg_carbs,
            "avg_daily_fats_g": avg_fats,
        },
    }


@app.get("/health")
def health_check():
    return {"status": "active", "elasticsearch": "connected" if es_client.ping() else "disconnected"}


@app.post("/api/recommend", response_model=RecommendationResponse)
def get_recommendation(request: QueryRequest):
    # ---------- 1. INTENT EXTRACTION (before generation) ----------
    intent = extract_intent(request.query)
    goal_type = intent["fitness_goal"]
    num_days = intent["num_days"]
    training_freq = intent["training_frequency_per_week"]
    target_body_parts = intent["target_body_parts"]

    target_muscles = []
    for part in target_body_parts:
        target_muscles.extend(BODY_PART_TO_MUSCLES.get(part, []))

    # ---------- 2. RETRIEVAL (body-part aware + diverse) ----------
    try:
        base_vector = model.encode(request.query).tolist()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating embedding: {str(e)}")

    # Exercises: enrich query with the requested body parts for better recall.
    ex_query = request.query
    if target_body_parts:
        ex_query = f"{request.query} {' '.join(target_body_parts)} exercises strength training"
    ex_vector = model.encode(ex_query).tolist()
    exercise_pool = search_elasticsearch("exercises", ex_vector, k=40)
    selected_exercises = select_exercises(exercise_pool, target_muscles, total=14)
    workout_options = [format_exercise(ex) for ex in selected_exercises]
    workout_summary = [
        {'index': i, 'name': ex['name'], 'target': ex['target_muscle'], 'equipment': ex['equipment']}
        for i, ex in enumerate(workout_options)
    ]

    # Recipes: pull a diverse pool from several angles to avoid repetition.
    snack_hints = {
        "weight_loss": "low calorie high fiber fruits vegetables light snacks",
        "muscle_gain": "high protein greek yogurt cottage cheese protein snacks",
        "recomp": "high protein low calorie lean snacks",
        "maintenance": "balanced nuts fruit whole grain snacks",
    }
    diet_text = " ".join(intent["dietary_restrictions"])
    main_recipes = search_elasticsearch("recipes", base_vector, k=45, filter_zero_macros=True)
    breakfast_vec = model.encode(f"{request.query} {diet_text} healthy breakfast eggs oats smoothie yogurt").tolist()
    breakfast_recipes = search_elasticsearch("recipes", breakfast_vec, k=12, filter_zero_macros=True)
    snack_vec = model.encode(f"{request.query} {diet_text} {snack_hints.get(goal_type, 'healthy snacks')}").tolist()
    snack_recipes = search_elasticsearch("recipes", snack_vec, k=15, filter_zero_macros=True)

    merged = {}
    for r in main_recipes + breakfast_recipes + snack_recipes:
        merged[r['id']] = r
    diverse_recipes = diversify_by_name(list(merged.values()), limit=30)
    catalog = [format_recipe_with_portions(r) for r in diverse_recipes]

    if not catalog:
        raise HTTPException(status_code=503, detail="No recipes with nutrition data are currently available.")

    # ---------- 3. NUTRITION SCIENCE (deterministic) ----------
    p = request.user_profile
    bmr = calculate_bmr(p.weight_kg, p.height_cm, p.age, p.sex)
    activity_factor = get_activity_factor(p.activity_level)
    tdee = calculate_tdee(bmr, activity_factor)
    _, calorie_adjustment = classify_goal(request.query)
    target_calories_initial = apply_goal_adjustment(tdee, calorie_adjustment)
    is_unsafe, target_calories, safety_warnings = detect_unsafe_goal(
        request.query, target_calories_initial, p.sex, tdee
    )
    target_protein_g, target_carbs_g, target_fats_g = compute_macro_targets(target_calories, p.weight_kg, goal_type)
    bmi = p.weight_kg / ((p.height_cm / 100) ** 2)

    # ---------- 4. LLM GENERATION ----------
    catalog_summary = [
        {
            "index": i,
            "name": r["recipe_name"],
            "calories": r["base_calories"],
            "protein_g": r["base_protein_g"],
            "carbs_g": r["base_carbs_g"],
            "fats_g": r["base_fats_g"],
            "prep_min": r["ready_in_minutes"],
            "ingredient_count": r["ingredient_count"],
            "tags": r["diet_tags"][:4],
            "snack_friendly": r["snack_friendly"],
            "meal_hint": r["meal_hint"],
        }
        for i, r in enumerate(catalog)
    ]

    body_focus_text = ", ".join(target_body_parts) if target_body_parts else "balanced full body"
    diet_restr_text = ", ".join(intent["dietary_restrictions"]) if intent["dietary_restrictions"] else "none"
    meal_prep_text = "YES - the user wants a repetitive meal-prep style plan" if intent["meal_prep_style"] else "NO - vary meals across days"

    llm_prompt = f"""You are a SENIOR NUTRITIONIST and CERTIFIED STRENGTH COACH. Build a realistic, professional, and personalized plan.

USER PROFILE: {p.age}y {p.sex}, {p.weight_kg}kg, {p.height_cm}cm, BMI: {bmi:.1f}
Activity Level: {p.activity_level}
User Request (verbatim): {request.query}

EXTRACTED INTENT (already parsed for you, respect it exactly):
- Fitness goal: {goal_type}
- Target body part focus: {body_focus_text}
- Training days per week: {training_freq}
- Dietary restrictions: {diet_restr_text}
- Number of days to generate: {num_days}
- Repetitive meal-prep style: {meal_prep_text}

INTERNAL DAILY TARGETS (use to choose portions, DO NOT mention any numbers in your text):
- Calories: ~{target_calories} kcal/day
- Protein: ~{target_protein_g} g/day
- Carbs: ~{target_carbs_g} g/day
- Fats: ~{target_fats_g} g/day

AVAILABLE RESOURCES:
- {len(catalog_summary)} recipes (single shared index space, use the "index" field)
- {len(workout_options)} exercises

STRICT RULES:
1. ALWAYS respond in ENGLISH.
2. Generate EXACTLY {num_days} day object(s) in "weekly_calendar". No more, no less.
3. Exactly {training_freq} of those days are TRAINING days (workout with exercises). The remaining days are REST days: set "is_rest_day": true, "exercise_indices": [], focus "Rest Day / Active Recovery".
4. WORKOUTS: prioritize the focus body part(s): {body_focus_text}. Give them more exercises and weekly volume, but keep the overall routine balanced (include other muscle groups and core across the week). If the focus is "balanced full body", spread exercises evenly.
5. Use ONLY recipe indices 0-{len(catalog_summary)-1} and exercise indices 0-{len(workout_options)-1}. Never invent items or numbers.
6. MEAL LOGIC (use common sense):
   - Breakfast must use breakfast-appropriate recipes (meal_hint "breakfast" preferred).
   - Lunch and Dinner use full "main" meals; do NOT put breakfast-only foods at dinner unless requested.
   - Snacks must be light/simple: prefer recipes with "snack_friendly": true (low calories, few ingredients, low prep time). Never assign a heavy full meal as a snack.
   - NEVER repeat the same recipe twice in the SAME day.
   - Unless meal-prep style is YES, do NOT repeat the exact same Breakfast or Dinner across all days; vary them.
7. MACRO DISTRIBUTION: a meal may combine 1-3 recipes (e.g., main dish + side, pancakes + eggs, smoothie + toast). Put 2-3 indices in "recipe_indices" with matching "portion_multipliers" when it helps hit the daily targets. Adjust portion_multipliers (0.5, 1.0, 1.5, 2.0) to land near the targets.
8. CONSISTENCY: keep daily calories and macros similar across days. The difference between the highest and lowest day must stay under 15%.
9. Include 2-3 snacks per day for balanced nutrition.
10. DO NOT include daily_totals (Python recalculates them). DO NOT mention calorie or macro numbers in any text field.

Return ONLY this exact JSON (ALL IN ENGLISH):
{{
  "plan_summary": {{
    "title": "Descriptive plan title reflecting the ACTUAL request (e.g. 'High-Protein Chest & Shoulder Plan')",
    "goal_detected": "short goal phrase reflecting the real request",
    "short_summary": "Brief explanation of the strategy",
    "focus": "Main training focus (must match the requested body part if any)",
    "difficulty_level": "Beginner/Intermediate/Advanced",
    "training_frequency_per_week": {training_freq},
    "target_body_parts": {json.dumps(target_body_parts)},
    "days_generated": {num_days}
  }},
  "weekly_calendar": [
    {{
      "day": "Monday",
      "is_rest_day": false,
      "meals": [
        {{"meal_type": "Breakfast", "recipe_indices": [0], "portion_multipliers": [1.5]}},
        {{"meal_type": "Morning Snack", "recipe_indices": [3], "portion_multipliers": [1.0]}},
        {{"meal_type": "Lunch", "recipe_indices": [5, 8], "portion_multipliers": [1.0, 0.5]}},
        {{"meal_type": "Afternoon Snack", "recipe_indices": [2], "portion_multipliers": [1.0]}},
        {{"meal_type": "Dinner", "recipe_indices": [12], "portion_multipliers": [1.5]}}
      ],
      "workout": {{"exercise_indices": [0,1,2,3], "focus": "Chest & Shoulders", "duration_min": 45}},
      "notes": "Short tip in English without mentioning specific numbers"
    }}
  ],
  "ai_recommendations": {{
    "main_tip": "Key advice (no numbers)",
    "personalized_notes": ["Observation about the user's profile", "Wellness tip"],
    "nutrition_tips": ["Meal timing tip", "Food quality tip"],
    "workout_tips": ["Training frequency advice", "Recovery tip"],
    "safety_notes": ["Safety consideration"]
  }}
}}"""

    full_prompt = f"""{llm_prompt}

RECIPE DATABASE (index 0-{len(catalog_summary)-1}):
{json.dumps(catalog_summary, indent=1)}

WORKOUT DATABASE (index 0-{len(workout_options)-1}):
{json.dumps(workout_summary, indent=1)}"""

    try:
        chat_completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": full_prompt}],
            temperature=0.3, max_tokens=4500,
            response_format={"type": "json_object"}
        )
        response_text = chat_completion.choices[0].message.content
        llm_data = json.loads(response_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI error: {str(e)}")

    weekly_calendar = llm_data.get('weekly_calendar', [])
    # Enforce the requested number of days defensively.
    if len(weekly_calendar) > num_days:
        weekly_calendar = weekly_calendar[:num_days]

    validation_result = validate_nutrition_plan(
        weekly_calendar, target_calories, target_protein_g, catalog
    )

    # Python is the single source of truth for daily_totals.
    recalculated_days = validation_result.get('recalculated_days', [])
    for i, day in enumerate(weekly_calendar):
        day['daily_totals'] = (
            recalculated_days[i]
            if i < len(recalculated_days)
            else {'calories': 0, 'protein_g': 0.0, 'carbs_g': 0.0, 'fats_g': 0.0}
        )
        day.setdefault('is_rest_day', len(day.get('workout', {}).get('exercise_indices', [])) == 0)

    ai_recommendations = llm_data.get('ai_recommendations', {})
    if safety_warnings:
        existing = ai_recommendations.get('safety_notes', [])
        ai_recommendations['safety_notes'] = safety_warnings + existing
    if not validation_result["weekly_balance"]["balanced"]:
        notes = ai_recommendations.get('safety_notes', [])
        notes.append("Daily calories/macros were not perfectly balanced across days; aim to keep portions consistent.")
        ai_recommendations['safety_notes'] = notes

    recalc_macros = validation_result['recalculated_macros']
    nutrition_summary = {
        "avg_daily_calories": recalc_macros['avg_daily_calories'],
        "avg_daily_protein_g": recalc_macros['avg_daily_protein_g'],
        "avg_daily_carbs_g": recalc_macros['avg_daily_carbs_g'],
        "avg_daily_fats_g": recalc_macros['avg_daily_fats_g'],
    }
    macro_bars = [
        {"label": "Calories", "value": recalc_macros['avg_daily_calories'], "unit": "kcal"},
        {"label": "Protein", "value": recalc_macros['avg_daily_protein_g'], "unit": "g"},
        {"label": "Carbs", "value": recalc_macros['avg_daily_carbs_g'], "unit": "g"},
        {"label": "Fats", "value": recalc_macros['avg_daily_fats_g'], "unit": "g"},
    ]

    plan_summary = llm_data.get('plan_summary', {})
    plan_summary.setdefault("training_frequency_per_week", training_freq)
    plan_summary.setdefault("target_body_parts", target_body_parts)
    plan_summary.setdefault("days_generated", len(weekly_calendar))

    complete_plan = {
        "plan_summary": plan_summary,
        "intent": intent,
        "user_profile_summary": {
            "age": p.age,
            "sex": p.sex,
            "weight_kg": p.weight_kg,
            "height_cm": p.height_cm,
            "bmi": round(bmi, 2),
            "activity_level": p.activity_level,
            "bmr": bmr,
            "tdee": tdee,
        },
        "nutrition_summary": nutrition_summary,
        "macro_bars": macro_bars,
        "weekly_balance": validation_result["weekly_balance"],
        "meal_options": catalog,
        "snack_options": [],
        "workout_options": workout_options,
        "weekly_calendar": weekly_calendar,
        "ai_recommendations": ai_recommendations,
    }
    return {
        "response": json.dumps(complete_plan, ensure_ascii=False),
        "plan": complete_plan,
        "raw_data": {"exercises": selected_exercises, "recipes": diverse_recipes},
    }
