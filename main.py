#!/usr/bin/env python3
import os
import re
import math
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

# =====================================================================
# WORKOUT / TRAINING-SPLIT RULES (Python-owned, deterministic)
# Sources reviewed (current strength-training consensus):
#   - Each major muscle group should be trained ~2-3x/week; twice-weekly
#     beats once-weekly at equal volume (BodySpec, BiologyInsights,
#     ScienceInsights, FitnessVolt 2025).
#   - ~10-20 hard sets per muscle group per week; 2-4 sets per exercise.
#   - Frequency drives the split: 3d full-body/PPL, 4d upper/lower,
#     5-6d PPL or upper/lower repeats so muscles get hit ~2x.
# Design: 6 resistance exercises per training day + goal-based cardio.
#   A requested body part becomes a PRIORITY: it gets its own focus
#   sessions ~2x/week (more slots), and the rest of the body is spread
#   across the remaining days as a balanced split.
# =====================================================================
EXERCISES_PER_DAY = 6

# Body-part group -> DB target_muscle values.
MUSCLE_GROUPS = {
    "chest": ["chest"],
    "back": ["lats", "middle back", "lower back", "traps"],
    "legs": ["quadriceps", "hamstrings", "glutes", "calves", "adductors", "abductors"],
    "shoulders": ["shoulders"],
    "arms": ["biceps", "triceps", "forearms"],
    "core": ["abdominals"],
}

# 6 muscle "slots" per training day (repeats = more volume for that muscle).
THEME_SLOTS = {
    "push":      ["chest", "chest", "shoulders", "shoulders", "triceps", "triceps"],
    "pull":      ["lats", "middle back", "traps", "biceps", "biceps", "forearms"],
    "legs":      ["quadriceps", "quadriceps", "hamstrings", "glutes", "calves", "abdominals"],
    "upper":     ["chest", "shoulders", "lats", "middle back", "biceps", "triceps"],
    "lower":     ["quadriceps", "hamstrings", "glutes", "calves", "adductors", "abdominals"],
    "full_body": ["quadriceps", "chest", "lats", "shoulders", "hamstrings", "abdominals"],
    "core":      ["abdominals", "abdominals", "lower back", "glutes", "quadriceps", "calves"],
}

THEME_LABEL = {
    "push": "Push (Chest, Shoulders, Triceps)",
    "pull": "Pull (Back, Biceps)",
    "legs": "Legs",
    "upper": "Upper Body",
    "lower": "Lower Body",
    "full_body": "Full Body",
    "core": "Core & Abs",
}

# Frequency -> ordered day themes (chosen so muscles recur ~2x at higher freq).
SPLIT_TEMPLATES = {
    1: ["full_body"],
    2: ["upper", "lower"],
    3: ["push", "pull", "legs"],
    4: ["upper", "lower", "push", "pull"],
    5: ["push", "pull", "legs", "upper", "lower"],
    6: ["push", "pull", "legs", "push", "pull", "legs"],
    7: ["push", "pull", "legs", "upper", "lower", "full_body", "core"],
}

# Cardio minutes per training day by goal (DB is strength-only, so cardio
# is expressed as a duration recommendation, not a retrieved exercise).
CARDIO_MIN_BY_GOAL = {
    "weight_loss": 25,
    "recomp": 20,
    "muscle_gain": 10,
    "maintenance": 15,
}
CARDIO_NOTE_BY_GOAL = {
    "weight_loss": "Finish with ~25 min moderate cardio (incline walk, cycling, or rower) to support the deficit.",
    "recomp": "Add ~20 min moderate cardio to support recomposition without hurting recovery.",
    "muscle_gain": "Keep cardio light (~10 min) to preserve energy for lifting and recovery.",
    "maintenance": "Add ~15 min steady cardio for cardiovascular health.",
}

SUPPORT_POOL = [
    "abdominals", "chest", "lats", "shoulders", "quadriceps",
    "biceps", "triceps", "hamstrings", "glutes", "calves",
]


def _spread_indices(num_days, count):
    """Evenly spread `count` picks across `num_days` (e.g. training vs rest)."""
    count = max(0, min(count, num_days))
    if count == 0:
        return []
    if count >= num_days:
        return list(range(num_days))
    if count == 1:
        return [0]
    return sorted(set(round(i * (num_days - 1) / (count - 1)) for i in range(count)))


def fetch_exercises_by_muscle(muscles, per_muscle=120):
    """Reliably fetch exercises for each muscle via an exact term query so a
    requested body part is ALWAYS represented (fixes 'asked for back, got none').
    Real training movements (with equipment) are ranked ahead of bodyweight
    stretch/mobility entries so the plan reads like a real workout."""
    # Stretch/mobility entries to push to the back of each bucket.
    mobility_terms = ("stretch", "smr", "circle", "mobility", "foam", "warm",
                      "dynamic", "static", "iytw", "pnf")
    quality_equipment = ("barbell", "dumbbell", "cable", "machine", "kettlebell",
                         "e-z curl bar", "bands")

    def score(ex):
        name = (ex.get("name") or "").lower()
        equip = (ex.get("equipment") or "").lower()
        s = 0
        if any(t in name for t in mobility_terms):
            s -= 10            # demote stretches/mobility
        if equip in quality_equipment:
            s += 3             # prefer loaded movements
        if equip in ("body only", "none", ""):
            s -= 1
        return s

    buckets = {}
    for m in set(muscles):
        try:
            resp = es_client.search(index="exercises", body={
                "size": per_muscle,
                "query": {"term": {"target_muscle": m}},
            })
            docs = [dict(h["_source"]) for h in resp["hits"]["hits"]]
            docs.sort(key=score, reverse=True)
            buckets[m] = docs
        except Exception as e:
            print(f"[ES WARN] muscle fetch '{m}' failed: {e}")
            buckets[m] = []
    return buckets


def _focus_day_slots(focus_muscles, support_muscles, support_offset=0):
    """A focus session: 4 slots for the focus muscles + 2 supporting slots.
    support_offset rotates which support muscles appear (variety across weeks)."""
    slots = [focus_muscles[i % len(focus_muscles)] for i in range(4)]
    if support_muscles:
        slots += [support_muscles[(support_offset + i) % len(support_muscles)] for i in range(2)]
    while len(slots) < EXERCISES_PER_DAY:
        slots.append(focus_muscles[len(slots) % len(focus_muscles)])
    return slots[:EXERCISES_PER_DAY]


def build_workout_week(num_days, training_freq, target_groups, goal_type):
    """Deterministically build the weekly split.
    Returns (workout_options, per_day) where per_day[i] is a dict with
    is_rest_day, focus, exercise_indices, duration_min, cardio_min, cardio_note."""
    training_freq = max(1, min(training_freq, num_days))
    training_idxs = set(_spread_indices(num_days, training_freq))

    # Resolve focus muscles from requested body-part groups (ignore non-muscle).
    focus_groups = [g for g in (target_groups or []) if g in MUSCLE_GROUPS]
    focus_muscles = []
    for g in focus_groups:
        for m in MUSCLE_GROUPS[g]:
            if m not in focus_muscles:
                focus_muscles.append(m)

    # Build the theme (muscle slots) for each TRAINING day position.
    day_themes = []  # list of (focus_label, [6 muscles])
    if focus_muscles:
        # Focus appears ~2x/week (3x at high frequency), spread out.
        n_focus = 1 if training_freq <= 1 else (3 if training_freq >= 6 else 2)
        n_focus = min(n_focus, training_freq)
        focus_positions = set(_spread_indices(training_freq, n_focus))
        support_muscles = [m for m in SUPPORT_POOL if m not in focus_muscles]
        focus_label = " & ".join(g.title() for g in focus_groups)
        # Residual themes cover the REST of the body on non-focus days.
        residual = [t for t in ["legs", "pull", "push", "lower", "upper", "core"]
                    if sum(1 for s in THEME_SLOTS[t] if s in focus_muscles) <= 3]
        if not residual:
            residual = ["legs", "pull", "push"]
        res_i = 0
        focus_seen = 0
        for pos in range(training_freq):
            if pos in focus_positions:
                day_themes.append((f"{focus_label} (Priority)", _focus_day_slots(focus_muscles, support_muscles, support_offset=focus_seen * 2)))
                focus_seen += 1
            else:
                t = residual[res_i % len(residual)]
                res_i += 1
                day_themes.append((THEME_LABEL[t], THEME_SLOTS[t]))
    else:
        base = SPLIT_TEMPLATES.get(training_freq, SPLIT_TEMPLATES[3])
        themes = [base[i % len(base)] for i in range(training_freq)]
        day_themes = [(THEME_LABEL[t], THEME_SLOTS[t]) for t in themes]

    # Fetch exercise candidates for every muscle we will use.
    needed = set()
    for _, slots in day_themes:
        needed.update(slots)
    buckets = fetch_exercises_by_muscle(list(needed))

    # Assign exercises with rotation (variety across days) + per-day uniqueness.
    pointers = {m: 0 for m in buckets}

    def pick_unique(muscle, used_ids):
        pool = buckets.get(muscle) or []
        if not pool:
            # Fallback: borrow from any non-empty bucket.
            for mm, pl in buckets.items():
                if pl:
                    pool = pl
                    muscle = mm
                    break
        if not pool:
            return None
        for _ in range(len(pool)):
            ex = pool[pointers[muscle] % len(pool)]
            pointers[muscle] += 1
            if ex.get("id") not in used_ids:
                return ex
        return None  # all exhausted (rare)

    selected = []           # unique exercises across the week
    id_to_index = {}
    cardio_min = CARDIO_MIN_BY_GOAL.get(goal_type, 15)
    cardio_note = CARDIO_NOTE_BY_GOAL.get(goal_type, "")

    per_day = []
    t_pos = 0
    for d in range(num_days):
        if d not in training_idxs:
            # Rest / active recovery; light cardio only when cutting.
            rest_cardio = 20 if goal_type == "weight_loss" else 0
            per_day.append({
                "is_rest_day": True,
                "focus": "Rest Day / Active Recovery",
                "exercise_indices": [],
                "duration_min": rest_cardio,
                "cardio_min": rest_cardio,
                "cardio_note": "Light walk or mobility work." if rest_cardio else "Rest, hydrate, and prioritize sleep.",
            })
            continue

        focus_label, slots = day_themes[t_pos]
        t_pos += 1
        used_ids = set()
        indices = []
        for muscle in slots:
            ex = pick_unique(muscle, used_ids)
            if not ex:
                continue
            used_ids.add(ex.get("id"))
            if ex.get("id") not in id_to_index:
                id_to_index[ex["id"]] = len(selected)
                selected.append(ex)
            indices.append(id_to_index[ex["id"]])

        per_day.append({
            "is_rest_day": False,
            "focus": focus_label,
            "exercise_indices": indices,
            "duration_min": len(indices) * 8 + cardio_min,
            "cardio_min": cardio_min,
            "cardio_note": cardio_note,
        })

    workout_options = [format_exercise(ex) for ex in selected]
    return workout_options, per_day

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

# =====================================================================
# MACRO PREFERENCES (generic, macro-aware retrieval & ranking)
# Each macro maps to: the recipe field, whether it's a "density" macro
# (judged as % of calories) or absolute, food words to seed retrieval for
# the "high" direction, and EN/ES keyword regexes for high/low intent.
# This is what lets ANY request ("low carb", "high fiber", "low calorie",
# "high fat", "high protein") rank by REAL macro values instead of names.
# =====================================================================
MACRO_CONFIG = {
    "protein": {
        "field": "protein_g",
        "kcal_per_g": 4,
        "density": True,
        "seed_high": "chicken breast beef steak fish salmon tuna eggs turkey shrimp lean meat greek yogurt cottage cheese lentils tofu",
        "high": r"high[\s-]?protein|protein[\s-]?rich|more protein|lots of protein|alta?\s+en\s+prote[ií]na|alto\s+en\s+prote[ií]na|mucha prote[ií]na|prote[ií]na alta",
        "low": r"low[\s-]?protein|baja?\s+en\s+prote[ií]na",
    },
    "carbs": {
        "field": "carbs_g",
        "kcal_per_g": 4,
        "density": True,
        "seed_high": "rice pasta potato bread oats quinoa noodles whole grains",
        "high": r"high[\s-]?carb|carb[\s-]?heavy|more carbs|alta?\s+en\s+carbohidratos|alto\s+en\s+carbohidratos",
        "low": r"low[\s-]?carb|low[\s-]?carbohydrate|keto|ketogenic|baja?\s+en\s+carbohidratos|bajo\s+en\s+carbohidratos|pocos carbohidratos|sin carbohidratos",
    },
    "fats": {
        "field": "fats_g",
        "kcal_per_g": 9,
        "density": True,
        "seed_high": "avocado olive oil nuts cheese salmon butter peanut butter",
        "high": r"high[\s-]?fat|keto|ketogenic|alta?\s+en\s+grasa|alto\s+en\s+grasa",
        "low": r"low[\s-]?fat|fat[\s-]?free|baja?\s+en\s+grasa|bajo\s+en\s+grasa|sin grasa",
    },
    "fiber": {
        "field": "fiber_g",
        "kcal_per_g": 0,
        "density": False,
        "seed_high": "beans lentils vegetables broccoli oats whole grains chia berries",
        "high": r"high[\s-]?fiber|high[\s-]?fibre|fiber[\s-]?rich|alta?\s+en\s+fibra|alto\s+en\s+fibra|mucha fibra",
        "low": r"low[\s-]?fiber|low[\s-]?fibre|baja?\s+en\s+fibra",
    },
    "calories": {
        "field": "calories",
        "kcal_per_g": 1,
        "density": False,
        "seed_high": "calorie dense hearty rich filling",
        "high": r"high[\s-]?calorie|calorie[\s-]?dense|more calories|alta?\s+en\s+calor[ií]as",
        "low": r"low[\s-]?calorie|low[\s-]?cal|light meals|baja?\s+en\s+calor[ií]as|bajo\s+en\s+calor[ií]as|pocas calor[ií]as",
    },
    "sugar": {
        "field": "sugar_g",
        "kcal_per_g": 4,
        "density": False,
        "seed_high": "",
        "high": r"high[\s-]?sugar",
        "low": r"low[\s-]?sugar|sugar[\s-]?free|no sugar|baja?\s+en\s+az[uú]car|sin az[uú]car",
    },
    "sodium": {
        "field": "sodium_mg",
        "kcal_per_g": 0,
        "density": False,
        "seed_high": "",
        "high": r"high[\s-]?sodium|high[\s-]?salt",
        "low": r"low[\s-]?sodium|low[\s-]?salt|baja?\s+en\s+sodio|bajo\s+en\s+sal|sin sal",
    },
}


def detect_macro_prefs(q):
    """Return a list of (macro, 'high'|'low') tuples found in the query.
    'low' is checked first so 'low fat' isn't caught by a 'fat' high rule."""
    prefs = []
    for macro, cfg in MACRO_CONFIG.items():
        if cfg.get("low") and re.search(cfg["low"], q):
            prefs.append((macro, "low"))
        elif cfg.get("high") and re.search(cfg["high"], q):
            prefs.append((macro, "high"))
    return prefs


# Common food/ingredient words we can recognize in free-text requests.
# Plurals/variants are handled by substring matching against the recipe text.
KNOWN_INGREDIENTS = [
    "protein powder", "whey protein", "whey", "casein", "protein shake",
    "peanut butter", "almond butter", "cottage cheese", "soy sauce", "olive oil",
    "chicken", "beef", "pork", "lamb", "turkey", "duck", "bacon", "ham", "sausage",
    "fish", "salmon", "tuna", "shrimp", "prawn", "crab", "lobster", "cod", "tilapia",
    "egg", "eggs", "milk", "cheese", "yogurt", "butter", "cream", "feta", "mozzarella",
    "garlic", "onion", "onions", "tomato", "tomatoes", "potato", "potatoes", "rice",
    "pasta", "noodles", "bread", "oats", "quinoa", "beans", "lentils", "chickpeas",
    "tofu", "mushroom", "mushrooms", "spinach", "broccoli", "cauliflower", "carrot",
    "carrots", "pepper", "peppers", "avocado", "corn", "peas", "cucumber", "lettuce",
    "peanut", "peanuts", "almond", "almonds", "walnut", "nuts", "cashew", "pecan",
    "shellfish", "soy", "gluten", "wheat", "sugar", "honey", "cilantro", "celery",
    "banana", "apple", "berries", "strawberry", "orange", "lemon", "lime", "coconut",
    "olive", "ginger", "chili", "cinnamon", "basil", "oregano", "parsley",
]

# Spanish -> English ingredient map so ES requests work too.
ES_INGREDIENT_MAP = {
    "pollo": "chicken", "carne": "beef", "res": "beef", "cerdo": "pork", "puerco": "pork",
    "cordero": "lamb", "pavo": "turkey", "tocino": "bacon", "jamon": "ham",
    "pescado": "fish", "salmon": "salmon", "atun": "tuna", "camaron": "shrimp", "camarones": "shrimp",
    "huevo": "egg", "huevos": "eggs", "leche": "milk", "queso": "cheese", "yogur": "yogurt",
    "mantequilla": "butter", "crema": "cream", "ajo": "garlic", "cebolla": "onion",
    "tomate": "tomato", "jitomate": "tomato", "papa": "potato", "papas": "potato", "patata": "potato",
    "arroz": "rice", "pasta": "pasta", "pan": "bread", "avena": "oats", "frijol": "beans",
    "frijoles": "beans", "lenteja": "lentils", "lentejas": "lentils", "champiñon": "mushroom",
    "champiñones": "mushrooms", "espinaca": "spinach", "brocoli": "broccoli", "zanahoria": "carrot",
    "aguacate": "avocado", "maiz": "corn", "cacahuate": "peanut", "cacahuates": "peanuts",
    "almendra": "almond", "nuez": "walnut", "nueces": "nuts", "soya": "soy", "azucar": "sugar",
    "miel": "honey", "platano": "banana", "manzana": "apple", "fresa": "strawberry",
    "naranja": "orange", "limon": "lemon", "coco": "coconut", "jengibre": "ginger",
}


# Synonyms / related terms so an exclusion blocks ALL variants (NLP-style).
# Excluding the key blocks every term in its list (and the key itself).
INGREDIENT_SYNONYMS = {
    "protein powder": ["protein powder", "whey", "whey protein", "protein isolate",
                        "whey isolate", "casein", "protein shake", "protein scoop",
                        "scoop of protein", "isolate", "mass gainer", "proteina en polvo",
                        "suero de leche", "protein blend", "plant protein", "pea protein"],
    "dairy": ["milk", "cheese", "yogurt", "yoghurt", "butter", "cream", "feta",
              "mozzarella", "ricotta", "parmesan", "cottage cheese", "whey", "casein"],
    "nuts": ["nuts", "peanut", "peanuts", "almond", "almonds", "walnut", "walnuts",
             "cashew", "cashews", "pecan", "pistachio", "hazelnut", "nut butter",
             "peanut butter", "almond butter"],
    "shellfish": ["shellfish", "shrimp", "prawn", "prawns", "crab", "lobster",
                  "clam", "mussel", "oyster", "scallop"],
    "fish": ["fish", "salmon", "tuna", "cod", "tilapia", "sole", "trout", "sardine",
             "anchovy", "halibut", "sea bass", "mackerel"],
    "pork": ["pork", "bacon", "ham", "sausage", "chorizo", "prosciutto"],
    "beef": ["beef", "steak", "ground beef", "sirloin", "brisket"],
    "chicken": ["chicken", "poultry"],
    "egg": ["egg", "eggs", "egg white", "egg yolk", "egg substitute", "egg beaters"],
    "gluten": ["gluten", "wheat", "flour", "bread", "pasta", "barley", "rye"],
    "sugar": ["sugar", "brown sugar", "syrup", "honey", "agave"],
    "soy": ["soy", "soya", "tofu", "edamame", "soy sauce", "tempeh"],
    "onion": ["onion", "onions", "scallion", "scallions", "shallot", "shallots", "leek", "leeks"],
    "garlic": ["garlic"],
    "mushroom": ["mushroom", "mushrooms", "shiitake", "portobello", "chanterelle"],
}


def _expand_excluded_terms_static(excluded):
    """Static, offline synonym expansion using the hardcoded INGREDIENT_SYNONYMS
    map. Always available — this is the allergy-safety floor that never depends
    on a network call."""
    terms = set()
    for ing in excluded:
        ing = ing.strip().lower()
        if not ing:
            continue
        terms.add(ing)
        if ing in INGREDIENT_SYNONYMS:
            terms.update(t.lower() for t in INGREDIENT_SYNONYMS[ing])
        for key, group in INGREDIENT_SYNONYMS.items():
            if ing == key or ing in group or any(ing in g or g in ing for g in group):
                terms.add(key)
                terms.update(t.lower() for t in group)
    return terms


# Cache LLM synonym lookups so repeat requests are cheap and deterministic.
_SYNONYM_CACHE = {}


def _llm_synonyms(excluded):
    """Ask the LLM to map each excluded ingredient to its synonyms / related
    surface forms found in recipe ingredient lists. Strict guardrails:
      - temperature 0 + JSON-only response_format (deterministic, same shape)
      - a fixed schema we validate; anything malformed is discarded
      - only short, lowercase, alphabetic food terms are kept (anti-hallucination)
      - results are merged with the static map, never used alone
    Returns a set of extra terms (may be empty on any failure)."""
    key = tuple(sorted(t.strip().lower() for t in excluded if t.strip()))
    if not key:
        return set()
    if key in _SYNONYM_CACHE:
        return _SYNONYM_CACHE[key]

    prompt = (
        "You expand food-exclusion terms for an allergy-safe meal filter. "
        "For each ingredient the user wants to AVOID, list other names, brands, "
        "and closely related forms that appear in recipe ingredient lists. "
        "Rules: only real food/ingredient words; lowercase; no phrases longer "
        "than 3 words; no explanations; do NOT invent unrelated foods. "
        "Return ONLY JSON of the exact shape: "
        '{"terms": ["term1", "term2", ...]}.\n'
        f"Ingredients to avoid: {', '.join(key)}"
    )
    try:
        resp = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        raw = data.get("terms", [])
        if not isinstance(raw, list):
            _SYNONYM_CACHE[key] = set()
            return set()
        clean = set()
        # Generic tokens that would over-match and wrongly remove safe recipes.
        too_generic = {"protein", "powder", "oil", "sauce", "spice", "spices",
                       "seasoning", "food", "meat", "drink", "supplement", "flavor",
                       "mix", "blend", "extract", "natural", "organic"}
        for t in raw:
            if not isinstance(t, str):
                continue
            t = t.strip().lower()
            # Guardrails: short, alphabetic (spaces allowed), <=3 words, not generic.
            if (t and len(t) <= 30 and len(t.split()) <= 3
                    and re.fullmatch(r"[a-z ]+", t) and t not in too_generic):
                clean.add(t)
        _SYNONYM_CACHE[key] = clean
        return clean
    except Exception as e:
        print(f"[synonyms] LLM expansion failed, using static map only: {e}")
        _SYNONYM_CACHE[key] = set()
        return set()


def expand_excluded_terms(excluded, use_llm=True):
    """Expand excluded ingredients into all synonyms/related terms so e.g.
    'protein powder' also blocks 'whey', 'casein', 'isolate'.
    Combines the hardcoded safety map (always) with optional LLM expansion
    (extra coverage). The static map guarantees allergy safety even if the LLM
    call fails or is disabled."""
    terms = _expand_excluded_terms_static(excluded)
    if use_llm and excluded:
        terms |= _llm_synonyms(excluded)
    return terms


def _find_ingredients(text):
    """Return the set of known ingredient words present in a text fragment."""
    found = set()
    for ing in KNOWN_INGREDIENTS:
        if re.search(rf'\b{re.escape(ing)}\b', text):
            found.add(ing)
    for es, en in ES_INGREDIENT_MAP.items():
        if re.search(rf'\b{re.escape(es)}\b', text):
            found.add(en)
    return found


def detect_ingredient_prefs(q):
    """Parse explicit ingredient include/exclude requests from the query.
    Returns (excluded, included). Exclusions are SAFETY-CRITICAL (allergies):
    handles 'no/without/avoid/don't include/allergic to/free of X', EN + ES.
    Inclusions handle 'with/include/lots of/as much X as possible'.
    """
    excluded, included = [], []

    # --- exclusion phrases: capture a SHORT fragment after the trigger ---
    # The fragment is length-bounded and stops at clause boundaries (pronouns/
    # verbs) so short lists like "peanuts and shellfish" or "garlic, onion" are
    # captured, but it won't run away into a separate clause like
    # "...and I want fish". _find_ingredients extracts known foods from it.
    STOP = r"(?:\.|;|$|\bi\b|\bplease\b|\bbut\b|\bwith\b|\bwant\b|\binclude\b|\bquiero\b|\bpor favor\b|\bpero\b|\bcon\b)"
    frag = r"([a-z][a-z, ]{0,40}?)"
    exclude_patterns = [
        rf"(?:no|without|avoid|skip|hold the|free of|free from|leave out|exclude|omit)\s+{frag}{STOP}",
        rf"(?:do(?:n't| not)|cannot|can't)\s+(?:include|eat|use|have)\s+{frag}{STOP}",
        rf"(?:allergic to|allergy to|intolerant to)\s+{frag}{STOP}",
        rf"(?:sin)\s+{frag}{STOP}",
        rf"(?:no\s+(?:incluir|incluyas|me gusta|puedo comer))\s+{frag}{STOP}",
        rf"(?:soy\s+al[eé]rgico\s+a(?:l)?)\s+{frag}{STOP}",
    ]
    for pat in exclude_patterns:
        for m in re.finditer(pat, q):
            excluded.extend(_find_ingredients(m.group(1)))

    # --- inclusion phrases ---
    include_patterns = [
        r"(?:with|include|including|add|using|use|lots of|plenty of|more)\s+([a-z, ]+?)(?:\.|,|;|$|\band\b|\bplease\b)",
        r"([a-z, ]+?)\s+as much as possible",
        r"(?:con|incluir|incluye|mucho|mucha|bastante)\s+([a-z, ]+?)(?:\.|,|;|$|\by\b)",
        r"([a-z, ]+?)\s+lo m[aá]s posible",
    ]
    for pat in include_patterns:
        for m in re.finditer(pat, q):
            included.extend(_find_ingredients(m.group(1)))

    # De-dupe; exclusions win over inclusions (safety first).
    excluded = list(dict.fromkeys(excluded))
    included = [i for i in dict.fromkeys(included) if i not in excluded]
    return excluded, included


def recipe_contains_ingredient(recipe, ingredient):
    """True if the recipe text (name + ingredients) mentions the ingredient.
    Uses word-boundary matching to avoid false hits (e.g. 'pea' in 'peanut')."""
    blob = f"{recipe.get('name','')} {recipe.get('ingredients','')}".lower()
    # Match the word and a simple plural form.
    return bool(re.search(rf'\b{re.escape(ingredient)}s?\b', blob))


def filter_excluded(recipes, excluded):
    """Remove every recipe that contains ANY excluded ingredient OR a synonym
    of it (allergy safety, hard filter). 'no protein powder' also removes whey,
    casein, isolate, protein shake, etc."""
    if not excluded:
        return recipes
    terms = expand_excluded_terms(excluded)
    out = []
    for r in recipes:
        blob = f"{r.get('name','')} {r.get('ingredients','')}".lower()
        if any(re.search(rf'\b{re.escape(t)}s?\b', blob) for t in terms):
            continue
        out.append(r)
    return out


def catalog_item_excluded(item, excluded_terms):
    """Final-catalog safety check using already-expanded synonym terms."""
    blob = f"{item.get('recipe_name','')} {item.get('ingredients','')}".lower()
    return any(re.search(rf'\b{re.escape(t)}s?\b', blob) for t in excluded_terms)


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
    # DEFAULT: train EVERY day (no rest) unless the user says otherwise.
    # Honors: explicit frequency ("5 days a week"), explicit rest days
    # ("2 rest days"), and "no/avoid rest days" / "every day".
    training_freq = None

    # Explicit "avoid/no rest days" or "every day" -> train all days.
    no_rest = bool(re.search(
        r'\b(no rest days?|without rest days?|avoid rest days?|skip rest days?|'
        r'every day|everyday|daily|all days?|sin d[ií]as? de descanso|todos los d[ií]as)\b', q
    ))

    # Explicit number of REST days requested -> derive training days.
    rest_days = None
    rm = re.search(r'(\d+)\s*(?:rest|recovery|off)\s*days?', q)
    if rm:
        rest_days = int(rm.group(1))
    else:
        for w, n in WORD_TO_NUM.items():
            if re.search(rf'\b{w}\s*(?:rest|recovery|off)\s*days?', q):
                rest_days = n
                break
        if rest_days is None and re.search(r'\b(a|one)\s*(?:rest|recovery|off)\s*day\b', q):
            rest_days = 1
    rm_es = re.search(r'(\d+)\s*d[ií]as?\s*de\s*descanso', q)
    if rest_days is None and rm_es:
        rest_days = int(rm_es.group(1))

    # Explicit training frequency ("5 days a week", "train 4 days", etc.).
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

    # Resolve precedence: explicit freq > rest-days > no-rest > default(all days).
    if training_freq is None:
        if rest_days is not None:
            training_freq = max(1, num_days - rest_days)
        elif no_rest:
            training_freq = num_days
        else:
            training_freq = num_days  # DEFAULT: workout every day
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

    # --- macro preferences (generic: applies to ANY macro the user mentions) ---
    # Each preference is (macro, direction): direction "high" or "low".
    # Detected from the query in English and Spanish. The retrieval + ranking
    # layer then orders recipes by the REAL macro value, not by name keywords
    # (so "high protein" returns chicken/beef, not "protein pancakes").
    macro_prefs = detect_macro_prefs(q)
    # Goal-driven defaults (only added if the user didn't say otherwise).
    pref_macros = {m for m, _ in macro_prefs}
    if "protein" not in pref_macros and goal_type in ("muscle_gain", "recomp"):
        macro_prefs.append(("protein", "high"))
    if "calories" not in pref_macros and goal_type == "weight_loss":
        macro_prefs.append(("calories", "low"))

    # --- explicit ingredient include / exclude (allergy-safe) ---
    excluded_ingredients, included_ingredients = detect_ingredient_prefs(q)
    # Vegetarian/vegan diets imply meat exclusions for safety/consistency.
    if "vegan" in restrictions:
        for w in ["chicken", "beef", "pork", "fish", "salmon", "tuna", "shrimp", "turkey",
                  "lamb", "egg", "eggs", "cheese", "milk", "yogurt", "butter", "honey"]:
            if w not in excluded_ingredients:
                excluded_ingredients.append(w)
    elif "vegetarian" in restrictions:
        for w in ["chicken", "beef", "pork", "fish", "salmon", "tuna", "shrimp", "turkey", "lamb"]:
            if w not in excluded_ingredients:
                excluded_ingredients.append(w)

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
        "macro_prefs": macro_prefs,
        "excluded_ingredients": excluded_ingredients,
        "included_ingredients": included_ingredients,
        # kept for backward compatibility / convenience
        "high_protein": any(m == "protein" and d == "high" for m, d in macro_prefs),
    }


# =====================================================================
# RETRIEVAL
# =====================================================================
def search_elasticsearch(index_name, query_vector, k=3, filter_zero_macros=False):
    # Fetch more candidates than k for re-ranking/filtering headroom.
    # ES requires num_candidates >= the knn `k`, so scale both together.
    # Also set top-level `size` (defaults to 10) so we actually return k docs.
    knn_k = max(k * 4, k)
    num_candidates = max(knn_k * 2, 200)
    search_query = {
        "knn": {"field": "embedding", "query_vector": query_vector, "k": knn_k, "num_candidates": num_candidates},
        "size": knn_k,
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


def macro_value(recipe, macro):
    """Absolute value of a macro from a recipe's macros block."""
    cfg = MACRO_CONFIG.get(macro, {})
    field = cfg.get("field", macro)
    return recipe.get("macros", {}).get(field, 0) or 0


def macro_density(recipe, macro):
    """Share of a recipe's calories that come from this macro (0-1).
    Used for energy macros (protein/carbs/fats) so we judge 'high protein'
    by how protein-dense the food really is, not by absolute grams alone."""
    cfg = MACRO_CONFIG.get(macro, {})
    cal = recipe.get("macros", {}).get("calories", 0) or 0
    if cal <= 0:
        return 0.0
    grams = macro_value(recipe, macro)
    return max(0.0, min(1.0, (grams * cfg.get("kcal_per_g", 0)) / cal))


# Backward-compatible protein helper used elsewhere
def protein_density(recipe):
    return macro_density(recipe, "protein")


def rank_by_macro_prefs(recipes, macro_prefs):
    """Order recipes to best satisfy the user's macro preferences, scoring by
    REAL macro values (not name keywords). Works for any macro/direction:
    high protein -> chicken/beef first; low carb -> low-carb dishes first; etc.

    Scoring per recipe = sum over prefs of a normalized contribution:
      - 'high' density macro: + (% calories from macro)
      - 'low'  density macro: + (1 - % calories from macro)
      - 'high' absolute macro (fiber/calories): + normalized rank
      - 'low'  absolute macro: + inverse normalized rank
    """
    if not macro_prefs or not recipes:
        return recipes

    # Precompute min/max for absolute macros to normalize.
    bounds = {}
    for macro, _ in macro_prefs:
        cfg = MACRO_CONFIG.get(macro, {})
        if not cfg.get("density"):
            vals = [macro_value(r, macro) for r in recipes]
            bounds[macro] = (min(vals), max(vals))

    def score(r):
        s = 0.0
        for macro, direction in macro_prefs:
            cfg = MACRO_CONFIG.get(macro, {})
            if cfg.get("density"):
                d = macro_density(r, macro)
                s += d if direction == "high" else (1.0 - d)
            else:
                lo, hi = bounds.get(macro, (0, 0))
                norm = (macro_value(r, macro) - lo) / (hi - lo) if hi > lo else 0.0
                s += norm if direction == "high" else (1.0 - norm)
        return s

    return sorted(recipes, key=score, reverse=True)


def build_balanced_catalog(recipes, macro_prefs, limit=30):
    """Build a catalog that PRIORITIZES the preferred macro but guarantees a
    realistic balance of carb and fat sources, so the LLM can assemble
    balanced days. Without this, a 'high protein' plan becomes all lean meat
    and the day's protein blows past safe limits.

    Strategy: rank by preference, then fill the catalog from three buckets:
      ~60% preferred (e.g. protein-dense), and reserve slots for carb-rich and
      fat/varied recipes so meals have something to pair protein with."""
    if not recipes:
        return []
    ranked = rank_by_macro_prefs(recipes, macro_prefs)
    ranked = diversify_by_name(ranked, limit=len(ranked))  # de-dupe by name

    wants_low_carb = any(m == "carbs" and d == "low" for m, d in macro_prefs)

    def carb_pct(r):
        return macro_density(r, "carbs")

    # Carb-rich recipes provide energy + variety to pair with lean protein.
    carb_rich = [r for r in ranked if carb_pct(r) >= 0.30]

    out, seen = [], set()
    def add(r):
        if r["id"] not in seen:
            seen.add(r["id"]); out.append(r)

    # Reserve carb slots unless the user explicitly wants low carb.
    carb_quota = 0 if wants_low_carb else max(4, int(limit * 0.30))

    # 1) Fill most of the catalog with the preference-ranked recipes.
    primary_target = limit - carb_quota
    for r in ranked:
        if len(out) >= primary_target:
            break
        add(r)
    # 2) Guarantee carb sources for balance.
    if carb_quota:
        for r in carb_rich:
            if len(out) >= limit:
                break
            add(r)
    # 3) Top up with anything remaining.
    for r in ranked:
        if len(out) >= limit:
            break
        add(r)
    return out[:limit]


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


def normalize_to_serving(cal, pro, carbs, fats):
    """FatSecret recipes often store WHOLE-RECIPE totals (several servings), so a
    single 'serving' can show e.g. 596 kcal / 117 g protein (~3 real servings).
    Scale every macro down by a single factor so ONE serving is realistic:
      - protein per serving <= ~45 g (a large chicken breast is ~45 g)
      - calories per serving <= ~700 kcal (a big single meal)
    Dividing all macros by the same factor preserves the recipe's macro ratios.
    """
    if cal <= 0:
        return cal, pro, carbs, fats, 1
    factor = max(
        1,
        math.ceil(pro / 45.0) if pro > 45 else 1,
        math.ceil(cal / 700.0) if cal > 700 else 1,
    )
    if factor <= 1:
        return cal, pro, carbs, fats, 1
    return (cal / factor, pro / factor, carbs / factor, fats / factor, factor)


def format_recipe_with_portions(recipe):
    base_macros = recipe.get('macros', {})
    raw_cal = base_macros.get('calories', 0) or 0
    raw_pro = base_macros.get('protein_g', 0) or 0
    raw_carbs = base_macros.get('carbs_g', 0) or 0
    raw_fats = base_macros.get('fats_g', 0) or 0
    # Normalize multi-serving recipe totals down to ONE realistic serving.
    base_cal, base_pro, base_carbs, base_fats, serving_factor = normalize_to_serving(
        raw_cal, raw_pro, raw_carbs, raw_fats
    )
    base_cal = int(round(base_cal))
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
        "servings_per_recipe": serving_factor,
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
# WEEKLY BALANCE (deterministic portion rebalancing)
# =====================================================================
PORTION_MIN = 0.5
PORTION_MAX = 2.5
PORTION_STEP = 0.25


def _day_calories(day, catalog):
    total = 0.0
    for meal in day.get('meals', []):
        ris = meal.get('recipe_indices', [])
        pms = meal.get('portion_multipliers', [1.0] * len(ris))
        if len(pms) < len(ris):
            pms = pms + [1.0] * (len(ris) - len(pms))
        for idx, mult in zip(ris, pms):
            if 0 <= idx < len(catalog):
                total += catalog[idx]['base_calories'] * mult
    return total


def _snap_portion(v):
    v = round(v / PORTION_STEP) * PORTION_STEP
    return round(max(PORTION_MIN, min(PORTION_MAX, v)), 2)


def rebalance_portions(weekly_calendar, catalog, target_calories, iterations=4):
    """Scale each day's portion multipliers toward the daily calorie target so
    that all days converge to a similar total. Pushing every day to the same
    target keeps the highest-vs-lowest spread well under the 15% limit.
    Multipliers are snapped to realistic 0.25 steps within [0.5, 2.5]."""
    if not weekly_calendar or target_calories <= 0:
        return
    for _ in range(iterations):
        max_rel_err = 0.0
        for day in weekly_calendar:
            day_cal = _day_calories(day, catalog)
            if day_cal <= 0:
                continue
            factor = target_calories / day_cal
            max_rel_err = max(max_rel_err, abs(day_cal - target_calories) / target_calories)
            for meal in day.get('meals', []):
                ris = meal.get('recipe_indices', [])
                pms = meal.get('portion_multipliers', [1.0] * len(ris))
                if len(pms) < len(ris):
                    pms = pms + [1.0] * (len(ris) - len(pms))
                meal['portion_multipliers'] = [_snap_portion(pm * factor) for pm in pms]
        if max_rel_err < 0.05:  # already within 5% of target on every day
            break


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
    # Flag protein that overshoots the safe ceiling (>15% over target).
    if target_protein_g and avg_pro > target_protein_g * 1.15:
        over_pct = int(((avg_pro - target_protein_g) / target_protein_g) * 100)
        warnings.append(f"Average protein above safe ceiling: {avg_pro}g vs {target_protein_g}g target ({over_pct:+d}%). Reduce protein portions and add carbs/fats.")

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

    # Exercises: build a deterministic weekly split (Python-owned).
    # The DB is strength-only; cardio is expressed as a per-day duration.
    workout_options, workout_per_day = build_workout_week(
        num_days, training_freq, target_body_parts, goal_type
    )
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
    macro_prefs = intent.get("macro_prefs", [])
    excluded_ingredients = intent.get("excluded_ingredients", [])
    included_ingredients = intent.get("included_ingredients", [])

    # Seed retrieval with REAL foods for any "high X" macro preference so the
    # candidate pool contains foods that actually satisfy the request (e.g.
    # high protein -> meat/fish/eggs; high fiber -> beans/veg; not name matches).
    seed_terms = []
    for macro, direction in macro_prefs:
        if direction == "high":
            seed = MACRO_CONFIG.get(macro, {}).get("seed_high", "")
            if seed:
                seed_terms.append(seed)
    # Bias retrieval toward explicitly requested ingredients ("chicken as much
    # as possible") so the pool is rich in them (still balanced later).
    if included_ingredients:
        seed_terms.append(" ".join(included_ingredients) + " " + " ".join(included_ingredients))
    if seed_terms:
        main_vec = model.encode(f"{request.query} {diet_text} {' '.join(seed_terms)}").tolist()
    else:
        main_vec = base_vector

    main_recipes = search_elasticsearch("recipes", main_vec, k=60, filter_zero_macros=True)
    wants_high_protein = any(m == "protein" and d == "high" for m, d in macro_prefs)
    breakfast_seed = "high protein breakfast eggs omelette greek yogurt cottage cheese" if wants_high_protein \
        else "healthy breakfast eggs oats smoothie yogurt"
    breakfast_vec = model.encode(f"{request.query} {diet_text} {breakfast_seed}").tolist()
    breakfast_recipes = search_elasticsearch("recipes", breakfast_vec, k=12, filter_zero_macros=True)
    snack_vec = model.encode(f"{request.query} {diet_text} {snack_hints.get(goal_type, 'healthy snacks')}").tolist()
    snack_recipes = search_elasticsearch("recipes", snack_vec, k=15, filter_zero_macros=True)

    # Always pull some carb/complex-carb sources so the catalog is never starved
    # of carbohydrates (otherwise a "high protein" plan becomes ALL meat and the
    # day's macros are unbalanced and unrealistically high in protein).
    carb_vec = model.encode(
        f"{request.query} {diet_text} rice pasta potato quinoa oats whole grain beans sweet potato vegetables fruit"
    ).tolist()
    carb_recipes = search_elasticsearch("recipes", carb_vec, k=20, filter_zero_macros=True)

    merged = {}
    for r in main_recipes + breakfast_recipes + snack_recipes + carb_recipes:
        merged[r['id']] = r
    pool = list(merged.values())

    # SAFETY-CRITICAL: hard-remove any recipe containing an excluded ingredient
    # (allergies / dislikes). This happens BEFORE ranking so excluded foods can
    # never appear in the plan.
    if excluded_ingredients:
        before = len(pool)
        pool = filter_excluded(pool, excluded_ingredients)
        print(f"[exclude] removed {before - len(pool)} recipes containing: {excluded_ingredients}")

    if not pool:
        raise HTTPException(
            status_code=422,
            detail=f"No recipes available after excluding: {', '.join(excluded_ingredients)}. Try removing some restrictions.",
        )

    # Prioritize explicitly included ingredients (e.g. "chicken as much as
    # possible") to the front of the pool, but keep variety so the plan still
    # includes other proteins/foods for balance.
    if included_ingredients:
        preferred = [r for r in pool if any(recipe_contains_ingredient(r, ing) for ing in included_ingredients)]
        others = [r for r in pool if r not in preferred]
        # ~65% preferred, rest kept for balance/variety.
        pool = preferred + others

    # Build a BALANCED catalog. When the user prefers a macro we prioritize it,
    # but we guarantee carb and fat sources remain so balanced meals are possible.
    if macro_prefs:
        diverse_recipes = build_balanced_catalog(pool, macro_prefs, limit=30)
    else:
        diverse_recipes = diversify_by_name(pool, limit=30)
    catalog = [format_recipe_with_portions(r) for r in diverse_recipes]

    # Final safety net: ensure no excluded ingredient (or synonym) slipped into
    # the catalog. Uses the SAME expanded synonym terms as the pool filter.
    if excluded_ingredients:
        _excl_terms = expand_excluded_terms(excluded_ingredients)
        catalog = [c for c in catalog if not catalog_item_excluded(c, _excl_terms)]

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
            # % of calories from each energy macro, so the LLM can judge a
            # protein-dense food (chicken) from a carby "protein pancake",
            # a low-carb dish from a carb-heavy one, etc.
            "protein_pct": (round((r["base_protein_g"] * 4) / r["base_calories"] * 100) if r["base_calories"] else 0),
            "carbs_pct": (round((r["base_carbs_g"] * 4) / r["base_calories"] * 100) if r["base_calories"] else 0),
            "fats_pct": (round((r["base_fats_g"] * 9) / r["base_calories"] * 100) if r["base_calories"] else 0),
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

    # Generic macro-preference rule for the LLM (works for any macro/direction).
    macro_prefs = intent.get("macro_prefs", [])
    if macro_prefs:
        pref_phrases = []
        for macro, direction in macro_prefs:
            if MACRO_CONFIG.get(macro, {}).get("density"):
                if direction == "high":
                    pref_phrases.append(f"{macro} (favor recipes with a high {macro}_pct; judge by real macros, NOT by the word '{macro}' in the name)")
                else:
                    pref_phrases.append(f"low {macro} (favor recipes with a low {macro}_pct)")
            else:
                pref_phrases.append(f"{direction} {macro}")
        macro_rule = (
            "\n   - MACRO PREFERENCES: the user wants " + "; ".join(pref_phrases) +
            ". Choose recipes whose ACTUAL macro values satisfy this, not recipes "
            "that merely mention the macro in their name."
        )
    else:
        macro_rule = ""

    # Ingredient include/exclude rules (exclude = allergy-safe, hard rule).
    excluded_ingredients = intent.get("excluded_ingredients", [])
    included_ingredients = intent.get("included_ingredients", [])
    ingredient_rule = ""
    if excluded_ingredients:
        ingredient_rule += (
            "\n   - FORBIDDEN INGREDIENTS (ALLERGY SAFETY - ABSOLUTE RULE): NEVER select any recipe "
            "that contains " + ", ".join(excluded_ingredients) + ". If unsure, skip the recipe."
        )
    if included_ingredients:
        ingredient_rule += (
            "\n   - PREFERRED INGREDIENTS: the user wants " + ", ".join(included_ingredients) +
            " as often as possible. Prioritize recipes featuring these, but keep variety with other "
            "proteins/foods across the week for a balanced plan."
        )

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
- Calories: ~{target_calories} kcal/day (keep each day within +/-10%)
- Protein: ~{target_protein_g} g/day. This is also a HARD CEILING — do NOT exceed {int(target_protein_g * 1.15)} g/day. Stop adding protein once you reach the target even if calories are still low; add carbs/fats instead.
- Carbs: ~{target_carbs_g} g/day (use carb-rich recipes to reach calories without overshooting protein)
- Fats: ~{target_fats_g} g/day

AVAILABLE RESOURCES:
- {len(catalog_summary)} recipes (single shared index space, use the "index" field)
- {len(workout_options)} exercises

STRICT RULES:
1. ALWAYS respond in ENGLISH.
2. Generate EXACTLY {num_days} day object(s) in "weekly_calendar". No more, no less.
3. The WORKOUT for each day is built separately by the system. You ONLY plan MEALS. Do NOT include a "workout" key. Match the day order: day 1 = "Monday", etc.
4. Use ONLY recipe indices 0-{len(catalog_summary)-1}. Never invent items or numbers.
5. MEAL LOGIC (use common sense):
   - Breakfast must use breakfast-appropriate recipes (meal_hint "breakfast" preferred).
   - Lunch and Dinner use full "main" meals; do NOT put breakfast-only foods at dinner unless requested.
   - Snacks must be light/simple: prefer recipes with "snack_friendly": true (low calories, few ingredients, low prep time). Never assign a heavy full meal as a snack.
   - NEVER repeat the same recipe twice in the SAME day.
   - Unless meal-prep style is YES, do NOT repeat the exact same Breakfast or Dinner across all days; vary them.{macro_rule}{ingredient_rule}
6. MACRO DISTRIBUTION: a meal may combine 1-3 recipes (e.g., main dish + side, pancakes + eggs, smoothie + toast). Put 2-3 indices in "recipe_indices" with matching "portion_multipliers" when it helps hit the daily targets. Adjust portion_multipliers (0.5, 1.0, 1.5, 2.0) to land near the targets.
7. CONSISTENCY: keep daily calories and macros similar across days. The difference between the highest and lowest day must stay under 15%.
8. Include 2-3 snacks per day for balanced nutrition.
9. DO NOT include daily_totals (Python recalculates them). DO NOT mention calorie or macro numbers in any text field.

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
      "meals": [
        {{"meal_type": "Breakfast", "recipe_indices": [0], "portion_multipliers": [1.5]}},
        {{"meal_type": "Morning Snack", "recipe_indices": [3], "portion_multipliers": [1.0]}},
        {{"meal_type": "Lunch", "recipe_indices": [5, 8], "portion_multipliers": [1.0, 0.5]}},
        {{"meal_type": "Afternoon Snack", "recipe_indices": [2], "portion_multipliers": [1.0]}},
        {{"meal_type": "Dinner", "recipe_indices": [12], "portion_multipliers": [1.5]}}
      ],
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
{json.dumps(catalog_summary, indent=1)}"""

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

    # Deterministically rebalance portions so daily calories/macros converge
    # toward the target (keeps day-to-day spread under the 15% limit).
    rebalance_portions(weekly_calendar, catalog, target_calories)

    validation_result = validate_nutrition_plan(
        weekly_calendar, target_calories, target_protein_g, catalog
    )

    # Python is the single source of truth for daily_totals AND workouts.
    recalculated_days = validation_result.get('recalculated_days', [])
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    for i, day in enumerate(weekly_calendar):
        day['day'] = day.get('day') or (day_names[i] if i < 7 else f"Day {i+1}")
        day['daily_totals'] = (
            recalculated_days[i]
            if i < len(recalculated_days)
            else {'calories': 0, 'protein_g': 0.0, 'carbs_g': 0.0, 'fats_g': 0.0}
        )
        # Inject the deterministic Python-built workout for this day.
        wd = workout_per_day[i] if i < len(workout_per_day) else None
        if wd:
            day['is_rest_day'] = wd['is_rest_day']
            day['workout'] = {
                "exercise_indices": wd['exercise_indices'],
                "focus": wd['focus'],
                "duration_min": wd['duration_min'],
                "cardio_min": wd['cardio_min'],
                "cardio_note": wd['cardio_note'],
            }
        else:
            day.setdefault('is_rest_day', True)
            day.setdefault('workout', {"exercise_indices": [], "focus": "Rest Day", "duration_min": 0, "cardio_min": 0, "cardio_note": ""})

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
        "raw_data": {"exercises": workout_options, "recipes": diverse_recipes},
    }
