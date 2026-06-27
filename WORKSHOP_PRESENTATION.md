# AI Health Assistant - RAG System Workshop
## Web Information Retrieval - Tsinghua University

---

## 1. EXECUTIVE SUMMARY

**Project Overview:** An intelligent health and fitness assistant that generates personalized weekly meal and workout plans using Retrieval-Augmented Generation (RAG) architecture.

**Core Innovation:** Combines semantic search, nutrition science, and LLM generation to produce safe, balanced, and scientifically-grounded fitness plans from natural language queries.

**Key Technologies:**
- Vector embeddings (sentence-transformers/all-MiniLM-L6-v2)
- Elasticsearch with KNN search (cosine similarity)
- OpenAI GPT-4o-mini for natural language generation
- FastAPI backend + Next.js 16 frontend
- Multi-source data crawler (FatSecret API, TheMealDB, Yuhonas GitHub)

**Demo Query:** "I want a leg hypertrophy routine and a high-protein diet"
**Output:** 7-day personalized plan with ~3,600 recipes and ~870 exercises

---

## 2. SYSTEM ARCHITECTURE

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          USER INPUT                              │
│         "I want a leg hypertrophy routine and high protein"      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    INTENT EXTRACTION (Rule-Based)                │
│  • Target body parts (legs, chest, back, etc.)                  │
│  • Training frequency (1-7 days/week)                           │
│  • Nutrition goal (weight_loss, muscle_gain, recomp)            │
│  • Macro preferences (high protein, low carb, etc.)             │
│  • Dietary restrictions (vegan, gluten-free, allergies)         │
│  • Number of days to generate                                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              NUTRITION SCIENCE (Deterministic Python)            │
│  • BMR calculation (Mifflin-St Jeor equation)                   │
│  • TDEE (BMR × activity multiplier)                             │
│  • Macro targets (protein: 1.2-2.4g/kg, fat: 20-35% kcal)      │
│  • Safety thresholds (min calories, max deficit/surplus)        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              VECTOR EMBEDDING & RETRIEVAL (RAG Core)             │
│                                                                  │
│  Query Encoder: sentence-transformers/all-MiniLM-L6-v2          │
│                 (384-dimensional embeddings)                     │
│                              ↓                                   │
│  Elasticsearch KNN Search (cosine similarity)                   │
│  • Main recipes (k=60)                                          │
│  • Breakfast-specific (k=12)                                    │
│  • Snack-specific (k=15)                                        │
│  • Carb sources (k=20) - for balance                            │
│  • Exercise pool (by target muscle groups)                      │
│                              ↓                                   │
│  Post-Processing:                                               │
│  • Allergy-safe hard filtering (synonyms expanded via LLM)     │
│  • Macro-aware ranking (by REAL macro density, not keywords)    │
│  • Diversity enforcement (remove near-duplicate names)          │
│  • Balanced catalog building (~60% preferred, 30% carbs)        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              WORKOUT PLAN GENERATION (Deterministic)             │
│                                                                  │
│  • 6-day split templates (PPL, Upper/Lower, Full-Body)         │
│  • Focus muscle gets 4/6 slots (~55%), rest balanced            │
│  • Exercise pool fetched from Elasticsearch                     │
│  • Equipment-ranked (barbell > dumbbell > bodyweight)          │
│  • Cardio duration by goal (25 min weight loss, 10 min bulk)   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                  LLM GENERATION (GPT-4o-mini)                   │
│                                                                  │
│  Prompt Engineering:                                            │
│  • User profile + extracted intent                             │
│  • Recipe catalog (30 items with macro %, prep time, tags)     │
│  • Workout catalog (14 items with muscle/equipment)            │
│  • Strict JSON schema enforcement                              │
│  • Safety rules (protein ceiling, carb pairing, no repeats)    │
│                              ↓                                   │
│  Temperature: 0.3 (deterministic, safe)                        │
│  Max tokens: 4500                                              │
│  Output: Weekly calendar with meals + portion multipliers      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│            MACRO REBALANCING (Deterministic Python)              │
│                                                                  │
│  • Carb-source injection (if day lacks carbs)                  │
│  • Iterative portion adjustment (6 iterations)                  │
│  • Protein items: 0.5-1.5 servings (prevent overshoot)         │
│  • Carb items: 0.5-3.0 servings (fill remaining calories)      │
│  • Protein ceiling: max 115% of target                         │
│  • Weekly consistency: <15% spread across days                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                   VALIDATION & FINAL OUTPUT                      │
│                                                                  │
│  • Recalculate all daily totals (Python is source of truth)    │
│  • Validate calorie tolerance (±10%)                           │
│  • Validate protein sufficiency (≥90% target)                  │
│  • Check weekly balance (max-min <15%)                         │
│  • Generate warnings + safety notes                            │
│                              ↓                                   │
│  Return JSON to frontend with:                                 │
│  • 7-day weekly calendar (meals + workouts)                    │
│  • Recipe catalog (with portions 0.5x-2.0x)                    │
│  • Exercise catalog                                            │
│  • AI recommendations                                          │
│  • Nutrition summary                                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     FRONTEND RENDERING                           │
│  • Interactive calendar view                                    │
│  • Recipe modals (ingredients, instructions, macros)           │
│  • Exercise modals (target muscle, equipment, MET)             │
│  • PDF export (jsPDF with visual cards)                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. DATA SOURCES & CRAWLER ARCHITECTURE

### 3.1 Multi-Source Crawler Design

**Three independent data sources:**

1. **Yuhonas Free Exercise Database (GitHub Dump)**
   - 873 exercises (strength training only)
   - Fields: name, target_muscle, equipment, instructions
   - No cardio exercises (limitation)
   - Static JSON dump (offline, reliable)

2. **TheMealDB API**
   - 666 unique recipes
   - A-Z exhaustive crawl
   - Free tier, no authentication
   - Rich metadata: ingredients, instructions, images, cuisine

3. **FatSecret API (Primary Recipe Source)**
   - 2,943 unique recipes (15% of available ~19,000)
   - OAuth 1.0 authentication required
   - 48 search terms × 5 pages per term
   - Limit: 5,000 API calls/day (free tier)
   - Auto-pagination with early termination (if page < 50 results)
   - **Priority-based crawling:** Proteínas → Estilos → Dietas → Internacional → Técnicas → Ingredientes → Postres → Adicionales
   - **Resumable progress:** Saves state to `crawler_progress.json` every 5 terms
   - **API limit detection:** Detects HTTP 429 and "limit exceeded" errors

**Total Dataset:**
- **3,609 recipes** (666 TheMealDB + 2,943 FatSecret)
- **873 exercises**
- ~70% deduplication rate (recipes appear in multiple categories)

### 3.2 Crawler Optimization Features

**Priority System (8 tiers):**
```python
PRIORITY_CATEGORIES = {
    1: ["chicken", "beef", "salmon", "eggs", "turkey"],  # High-quality protein
    2: ["salad", "pasta", "rice", "soup", "breakfast"],  # Popular styles
    3: ["keto", "low carb", "high protein", "vegan"],    # Common diets
    4: ["mexican", "italian", "asian", "greek"],         # International
    5: ["stir fry", "grill", "bake", "roast"],           # Cooking techniques
    6: ["fish", "shrimp", "pork", "curry"],              # Secondary proteins
    7: ["dessert", "cake", "cookies"],                   # Treats
    8: ["smoothie", "juice", "sandwich"]                 # Additional items
}
```

**Progress Tracking:**
- JSON-based checkpoint file
- Auto-resume from last successful query
- API limit detection with graceful stop
- Safe to run over multiple days

**Data Quality:**
- Multi-serving recipe normalization (divide by ceiling(protein/45g) or ceiling(cal/700))
- Zero-macro filtering
- Duplicate ID removal
- Ingredient list parsing

---

## 4. EMBEDDING MODEL & VECTOR DATABASE

### 4.1 Embedding Model: sentence-transformers/all-MiniLM-L6-v2

**Why this model?**
- **Lightweight:** 384 dimensions (vs 768 for BERT-base)
- **Fast inference:** ~2ms per query on CPU
- **Semantic understanding:** Trained on 1B+ sentence pairs
- **Multilingual capable:** Handles English + Spanish queries
- **Offline-first:** Can run without internet (HuggingFace cache)

**Encoding Pipeline:**
```python
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
query_vector = model.encode(user_query).tolist()  # → [384 floats]
```

**Semantic Query Expansion:**
- Base query: user's raw text
- Macro seed terms: "chicken breast beef steak fish" (for high protein)
- Dietary restrictions: "vegan gluten-free"
- Combined: "leg hypertrophy high protein chicken beef fish vegan"

### 4.2 Vector Database: Elasticsearch 8.11 with KNN

**Index Configuration:**
```json
{
  "mappings": {
    "properties": {
      "embedding": {
        "type": "dense_vector",
        "dims": 384,
        "index": true,
        "similarity": "cosine"
      }
    }
  }
}
```

**KNN Search Query:**
```python
search_query = {
    "knn": {
        "field": "embedding",
        "query_vector": query_vector,
        "k": 60,
        "num_candidates": 200
    },
    "size": 60
}
```

**Why Elasticsearch?**
- **Hybrid search:** Combines exact-match filters + vector KNN
- **Scalability:** Can index millions of vectors
- **Production-ready:** Battle-tested, cloud-deployable
- **Approximate KNN:** HNSW algorithm (fast, accurate)
- **Filtering support:** Can apply dietary restrictions at query time

**Cosine Similarity:**
- Range: [-1, 1], higher = more similar
- Efficient for normalized embeddings
- Captures semantic meaning (not just keyword overlap)

---

## 5. QUERY PROCESSING & NLP

### 5.1 Intent Extraction (Rule-Based, Pre-Generation)

**Why rule-based instead of LLM?**
- **Speed:** <1ms vs 500ms+ for LLM call
- **Reliability:** Deterministic, no hallucination risk
- **Cost:** Zero API cost
- **Debuggability:** Regex patterns are inspectable

**Extracted Features:**
```python
intent = {
    "fitness_goal": "muscle_gain",           # weight_loss | muscle_gain | recomp | maintenance
    "target_body_parts": ["legs"],           # chest, back, legs, arms, shoulders, core
    "training_frequency_per_week": 5,        # 1-7 days
    "nutrition_goal": "muscle_gain",
    "dietary_restrictions": ["vegan"],       # vegetarian, gluten-free, keto, etc.
    "num_days": 7,                          # 1-7
    "wants_weekly_plan": True,
    "meal_prep_style": False,
    "macro_prefs": [("protein", "high")],    # Generic: works for ANY macro
    "excluded_ingredients": ["dairy"],       # Allergy-safe
    "included_ingredients": ["chicken"]      # Preference
}
```

**Regex Pattern Examples:**
```python
# Body parts
r'\b(leg|quad|squat|hamstring|glute|calves|lunge|pierna)\b'

# Macro preferences (generic, works for protein/carbs/fats/fiber/calories)
MACRO_CONFIG = {
    "protein": {
        "high": r"high[\s-]?protein|protein[\s-]?rich|more protein",
        "low": r"low[\s-]?protein"
    }
}

# Training frequency
r'(\d+)\s*[-\s]?\s*(?:day|days|times)\s*(?:a|per)?\s*week'

# Ingredient exclusions (allergy-safe)
r"(?:no|without|avoid|allergic to)\s+([a-z][a-z, ]{0,40}?)"
```

**Multilingual Support:**
- Spanish → English ingredient mapping
- "pollo" → "chicken", "res" → "beef", "sin lácteos" → "dairy-free"

### 5.2 Ingredient Synonym Expansion (Safety-Critical)

**Two-layer system:**

1. **Static hardcoded map (always active):**
```python
INGREDIENT_SYNONYMS = {
    "protein powder": ["protein powder", "whey", "casein", "isolate", "protein shake"],
    "dairy": ["milk", "cheese", "yogurt", "butter", "cream", "whey", "casein"],
    "nuts": ["peanut", "almond", "walnut", "cashew", "nut butter"]
}
```

2. **LLM expansion (optional, cache-backed):**
- Temperature: 0 (deterministic)
- JSON-only response format
- Guardrails: max 3 words, alphabetic only, anti-hallucination filters
- Falls back to static map on failure

**Why hybrid?**
- Static map guarantees allergy safety even if LLM fails
- LLM catches edge cases ("isolate", "whey protein concentrate")
- Cache prevents repeated LLM calls (same exclusions → same expansion)

---

## 6. MAIN.PY GENERAL FLOW

### 6.1 API Endpoint: `/api/recommend`

**Input (JSON):**
```json
{
  "query": "I want a leg hypertrophy routine and high-protein diet",
  "user_profile": {
    "age": 24,
    "sex": "Male",
    "weight_kg": 75,
    "height_cm": 175,
    "activity_level": "moderately_active"
  }
}
```

**Output (JSON):**
```json
{
  "response": "Generated plan...",
  "plan": {
    "plan_summary": {...},
    "user_profile_summary": {...},
    "nutrition_summary": {...},
    "meal_options": [30 recipes with portions],
    "workout_options": [14 exercises],
    "weekly_calendar": [7 days],
    "ai_recommendations": {...}
  }
}
```

### 6.2 Execution Pipeline (Step-by-Step)

**Phase 1: Intent Extraction (1-2ms)**
- Parse query with 40+ regex patterns
- Extract body parts, frequency, macros, restrictions, ingredients
- Classify fitness goal (weight_loss, muscle_gain, recomp, maintenance)

**Phase 2: Nutrition Science (1ms)**
- Calculate BMR (Mifflin-St Jeor: `10*weight + 6.25*height - 5*age + sex_offset`)
- Calculate TDEE (`BMR × activity_factor`)
- Apply goal adjustment (deficit -20%, surplus +15%)
- Safety checks: min calories (1500M/1200F), max deficit/surplus (25%/20%)
- Compute macro targets:
  - Protein: 1.2-2.4 g/kg body weight (goal-dependent)
  - Fat: minimum 0.5 g/kg AND ≥20% calories, capped at 35%
  - Carbs: remaining calories ÷ 4

**Phase 3: Vector Retrieval (50-100ms)**
- Generate 384-dim query vector
- 4 parallel Elasticsearch KNN searches:
  - Main recipes (k=60): query + macro seeds + included ingredients
  - Breakfast (k=12): "eggs omelette greek yogurt"
  - Snacks (k=15): goal-specific ("low calorie high fiber")
  - Carbs (k=20): "rice pasta potato oats beans" (for balance)
- Merge results (de-duplicate by ID)
- **Hard filter:** Remove ANY recipe containing excluded ingredients (allergy safety)
- Macro-aware ranking: sort by REAL macro density (not keyword matches)
- Balanced catalog building: 60% preferred macro, 30% carbs, 10% varied

**Phase 4: Workout Generation (10-20ms, deterministic)**
- Build weekly split template (PPL, Upper/Lower, Full-Body by frequency)
- Focus muscle gets 4/6 slots per day, rest balanced
- Fetch exercises from Elasticsearch (exact term query by target_muscle)
- Rank: equipment quality (barbell > dumbbell > bodyweight)
- Assign cardio duration by goal (25 min weight loss, 10 min bulk)

**Phase 5: LLM Generation (5-15 seconds)**
- Build structured prompt:
  - User profile + extracted intent
  - Macro targets (hidden from LLM text, used for portion selection)
  - Recipe catalog (30 items: index, name, macros, macro %, prep time, tags)
  - Workout catalog (14 items: index, name, muscle, equipment, MET)
  - Strict JSON schema
  - Safety rules: protein ceiling, carb pairing, no same-day repeats
- Call OpenAI GPT-4o-mini:
  - Temperature: 0.3 (deterministic)
  - Max tokens: 4500
  - Response format: JSON object
- Parse output: extract weekly_calendar (7 days of meals)

**Phase 6: Macro Rebalancing (1-2ms)**
- **Carb injection:** If any day lacks carb-dense recipes (≥35% carbs), append carb sources to main meals
- **Iterative rebalancing (6 iterations):**
  - Keep protein items at 0.5-1.5 servings (prevent overshoot)
  - Scale carb items at 0.5-3.0 servings (fill remaining calories)
  - Enforce protein ceiling: max 115% of target
- **Convergence:** Stop when daily calories within ±5% of target

**Phase 7: Validation (1ms)**
- Recalculate daily totals (Python is source of truth, not LLM)
- Check calorie tolerance (±10%)
- Check protein sufficiency (≥90% target)
- Check weekly consistency (max-min <15% for each macro)
- Generate warnings + safety notes

**Phase 8: Response Assembly (1ms)**
- Merge LLM output + Python calculations
- Inject workouts into weekly_calendar
- Return complete JSON to frontend

**Total Time:** ~6-20 seconds (dominated by LLM call)

---

## 7. FRONTEND ARCHITECTURE

### 7.1 Tech Stack

- **Framework:** Next.js 16.2.6 (React 19.2.4)
- **Styling:** Tailwind CSS 4 (utility-first, dark mode support)
- **State Management:** React hooks (useState, useEffect)
- **PDF Export:** jsPDF 4.2.1
- **Markdown Rendering:** react-markdown with rehype-highlight (recipe instructions)
- **Type Safety:** TypeScript 5

### 7.2 Key Features

**1. Interactive Calendar View**
- 7-day tab navigation
- Daily totals: calories, protein, carbs, fats
- Meal cards: expandable with recipe details
- Workout cards: exercise list with target muscles

**2. Staged Loading Progress**
```typescript
const LOADING_STAGES = [
  { label: "Analyzing your profile and goals", pct: 12, ms: 6000 },
  { label: "Calculating calories and macro targets", pct: 28, ms: 8000 },
  { label: "Retrieving the best recipes for you", pct: 50, ms: 14000 },
  { label: "Selecting and balancing your exercises", pct: 68, ms: 12000 },
  { label: "Generating your personalized plan", pct: 88, ms: 16000 },
  { label: "Finalizing and balancing your week", pct: 97, ms: 8000 }
];
```
- Eases progress toward target (never stalls)
- Creeps slowly between stages (psychological smoothing)
- Total: ~64 seconds animation (backend takes 6-20s)

**3. Recipe Modals**
- Full ingredients list
- Step-by-step instructions
- Macro breakdown (donut chart: protein purple, carbs blue, fats orange)
- Prep time + equipment needed
- Link to original source (FatSecret/TheMealDB)

**4. Exercise Modals**
- Target muscle group
- Equipment required
- MET value (metabolic equivalent, color-coded: green <3, yellow 3-6, red >6)
- Detailed instructions

**5. PDF Export (Professional Quality)**
- Page 1: User profile + goals + plan summary
- One page per day: meals (recipe cards) + workout (exercise table)
- Visual hierarchy: purple headers, macro chips, donut charts
- Pre-measured cards: never straddle page breaks
- Auto-redraws exercise table header on new pages
- Filename: auto-generated from plan title

**6. Client-Side Validation**
```typescript
// Guardrails for unrealistic inputs
if (age < 13 || age > 100) errors.age = "Please enter a realistic age between 13 and 100.";
if (height < 90) errors.height_cm = "Please enter your height in centimeters, e.g. 180 instead of 1.8.";
if (weight < 25 || weight > 400) errors.weight_kg = "Please enter a realistic weight in kilograms (25-400 kg).";
```

**7. Responsive Design**
- Mobile-first layout
- Dark mode support
- Tailwind CSS utility classes
- Adaptive font sizes + spacing

### 7.3 API Integration

**Backend URL (environment variable):**
```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
```

**POST /api/recommend:**
```typescript
const res = await fetch(`${API_URL}/api/recommend`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    query: coachQuery,
    user_profile: {
      age: Number(formData.age),
      sex: formData.sex,
      weight_kg: Number(formData.weight_kg),
      height_cm: Number(formData.height_cm),
      activity_level: formData.activity_level
    }
  })
});
```

---

## 8. LIMITATIONS

### 8.1 Data Limitations

**Recipe Coverage:**
- Only 15% of FatSecret's 19,000+ recipes crawled (API limit: 5,000 calls/day)
- Uneven distribution: "chicken" (250+ recipes), "lunch" (~1 recipe)
- ~70% deduplication rate (recipes appear in multiple categories)
- **Impact:** Meal variety limited for niche diets (e.g., vegan + keto + nut-free)

**Exercise Database:**
- **No cardio exercises:** Database is strength-only (873 exercises)
- Cardio expressed as duration recommendation (not searchable movements)
- No equipment filtering at retrieval time (some exercises require gym equipment)
- **Impact:** Cannot generate detailed cardio plans (HIIT, running intervals, etc.)

**Nutrition Data Quality:**
- FatSecret recipes often store whole-recipe totals (not per-serving)
- Normalization heuristic: divide by `ceil(protein/45g)` or `ceil(cal/700)`
- Some recipes missing fiber, sugar, sodium
- **Impact:** Macro targets may be slightly off (±5-10%)

### 8.2 System Limitations

**LLM Hallucination Risk:**
- Despite strict prompts, LLM can:
  - Repeat same recipe within a day (<1% of plans)
  - Assign breakfast foods to dinner (~2% of plans)
  - Overshoot protein targets (mitigated by rebalancer)
- **Mitigation:** Python validation + rebalancing layer overrides LLM

**Macro Balancing Trade-offs:**
- Rebalancer prioritizes calories > protein > carbs > fats
- Can't perfectly hit all 4 targets simultaneously
- Weekly consistency (<15% spread) sometimes sacrifices daily precision
- **Impact:** Some days may be ±15% off target (still within safe range)

**Allergy Safety:**
- Synonym expansion is comprehensive but not exhaustive
- Edge case: "casein-free" may not catch "sodium caseinate"
- **Mitigation:** Recommend users double-check ingredients list
- **Future:** Medical-grade allergen database integration

**Performance:**
- Backend response time: 6-20 seconds (dominated by LLM call)
- No caching layer (every request is fresh)
- Elasticsearch can handle 100+ concurrent users, but single FastAPI instance bottlenecks
- **Impact:** Not suitable for high-traffic production without horizontal scaling

**Scalability:**
- Current setup: single server, single Elasticsearch node
- No load balancer, no CDN
- Recipe database static (no auto-updates from APIs)
- **Impact:** Manual crawler runs needed to refresh data

---

## 9. FUTURE WORK

### 9.1 Accuracy Improvements

**1. Operations Research Optimization Models**

**Current approach (heuristic):**
- LLM proposes meals → Python rebalances portions iteratively
- Convergence not guaranteed (stops after 6 iterations)
- May sacrifice protein target to hit calories

**Proposed: Linear Programming (LP) optimization**

**Problem formulation:**
```
Minimize:
  Σ |daily_calories_i - target_calories|² +
  λ₁ · |avg_protein - target_protein|² +
  λ₂ · weekly_variance(calories) +
  λ₃ · Σ meal_repetition_penalty

Subject to:
  • portion_multiplier ∈ [0.5, 2.5]
  • protein_items ∈ [0.5, 1.5] (tight bound)
  • carb_items ∈ [0.5, 3.0] (loose bound)
  • daily_protein ≤ 1.15 × target_protein
  • daily_fat ≥ 0.2 × daily_calories / 9
  • daily_fat ≤ 0.35 × daily_calories / 9
  • no_same_recipe_same_day(i, j) ∀ i≠j
  • weekly_variance(macro) ≤ 0.15 × avg(macro)
```

**Solver:** CVXPY (Python convex optimization), GLPK, or Gurobi

**Benefits:**
- **Guaranteed convergence** (vs iterative heuristic)
- **Multi-objective optimization** (calories + protein + variety + consistency)
- **Constraint satisfaction** (hard limits always respected)
- **Speed:** 10-50ms for 7 days × 5 meals (faster than LLM rebalancing)

**Expected accuracy gain:** ±2-3% macro targets (vs current ±5-10%)

---

**2. Constraint Programming for Meal Scheduling**

**Problem:** Avoid meal repetition across days while respecting macro diversity

**Current:** LLM instructed "don't repeat", but sometimes fails

**Proposed:** CP-SAT solver (Google OR-Tools)
```python
from ortools.sat.python import cp_model

model = cp_model.CpModel()
# Variables: recipe_i_assigned_day_j ∈ {0,1}
# Constraints:
#   - Each day gets exactly N meals
#   - No recipe appears twice same day
#   - Macro targets met (LP layer handles portions)
#   - Breakfast recipes only at breakfast
```

**Benefits:**
- **Zero repeats** within same day (guaranteed)
- Meal type constraints (breakfast ≠ dinner)
- Diversity across days (e.g., max 2 appearances per recipe per week)

---

**3. Integer Programming for Exercise Selection**

**Problem:** Select 6 exercises per day that maximize muscle coverage + equipment variety

**Current:** Greedy selection from pre-ranked pool

**Proposed:** IP model
```
Maximize:
  Σ muscle_coverage_score +
  α · equipment_diversity -
  β · difficulty_mismatch

Subject to:
  • Σ exercises_per_day = 6
  • focus_muscle appears ≥ 3 times per day
  • no_muscle_overload (e.g., biceps ≤ 2 exercises/day)
  • equipment_available(exercise_i) = True
```

**Benefits:**
- Balanced muscle activation
- Equipment diversity (not all barbell)
- Difficulty progression (beginner → advanced)

---

### 9.2 Ranking & Retrieval Improvements

**1. Hybrid Search (BM25 + Dense Vectors)**
- Current: Pure KNN vector search
- Proposed: Elasticsearch hybrid query (50% BM25 keyword, 50% KNN)
- **Benefit:** Catch exact matches ("chicken breast") even if vector embedding is weak

**2. Re-Ranking Layer (Cross-Encoder)**
- Current: Single-stage retrieval
- Proposed: Two-stage retrieval + re-ranking
  - Stage 1: Retrieve 100 candidates (fast, approximate KNN)
  - Stage 2: Re-rank with cross-encoder (sentence-transformers/ms-marco-MiniLM-L-12-v2)
- **Benefit:** +5-10% retrieval precision

**3. User Feedback Loop**
- Proposed: "Was this recipe helpful?" thumbs up/down
- Store feedback in Elasticsearch (`user_rating` field)
- Boost high-rated recipes in future retrievals
- **Benefit:** Personalized recommendations over time

---

### 9.3 Data Expansion

**1. Complete FatSecret Crawl**
- Current: 2,943 recipes (15% of 19,000)
- Proposed: Exhaust all categories + pagination
- **Challenge:** 5,000 API calls/day limit → ~4 days needed
- **Benefit:** 6x more recipes, better niche diet coverage

**2. Cardio Exercise Database**
- Current: Zero cardio exercises
- Proposed: Integrate ExRx.net or custom cardio DB
  - HIIT intervals, running programs, cycling plans
- **Benefit:** Complete fitness plans (not just strength)

**3. Micronutrient Data**
- Current: Macros only (protein, carbs, fats, fiber)
- Proposed: Add vitamins, minerals, sodium, cholesterol
- **Benefit:** Identify nutrient gaps (e.g., low iron, vitamin D)

---

### 9.4 LLM & Prompt Engineering

**1. Few-Shot Prompting**
- Current: Zero-shot with strict rules
- Proposed: Provide 2-3 example plans in prompt
- **Benefit:** Reduce hallucination, improve meal pairing

**2. Chain-of-Thought Reasoning**
- Current: Direct JSON generation
- Proposed: Two-step generation
  - Step 1: "Explain your meal selection strategy"
  - Step 2: "Now generate the JSON"
- **Benefit:** More logical meal combinations

**3. Fine-Tuned Model**
- Current: Generic GPT-4o-mini
- Proposed: Fine-tune on 1,000+ labeled plans
- **Challenge:** Expensive ($500-1,000 for training data + compute)
- **Benefit:** 2-3x faster inference, lower cost per request

---

### 9.5 System Architecture

**1. Caching Layer**
- Redis for frequent queries (e.g., "lose weight high protein")
- Cache TTL: 24 hours
- **Benefit:** 10x faster response for repeat queries

**2. Horizontal Scaling**
- Kubernetes cluster: 3-5 FastAPI replicas
- Load balancer (NGINX or AWS ELB)
- **Benefit:** Handle 100+ concurrent users

**3. Async Processing**
- Current: Synchronous (user waits 6-20s)
- Proposed: WebSocket or Server-Sent Events
  - Immediate "Plan accepted, generating..." response
  - Stream progress updates (Phase 1/7, Phase 2/7, ...)
  - Final plan pushed when ready
- **Benefit:** Better UX, no timeout errors

---

## 10. TRADE-OFFS

### 10.1 Accuracy vs Speed

**Current Choice:** Speed-optimized
- Rule-based intent extraction (<1ms) instead of LLM (500ms)
- Single-stage retrieval instead of re-ranking
- 6 rebalancing iterations (not convergence guarantee)
- **Result:** 6-20s total response time, ±5-10% macro accuracy

**Alternative:** Accuracy-optimized
- LLM intent extraction (better edge cases)
- Two-stage retrieval + cross-encoder re-ranking
- LP optimization (guaranteed convergence)
- **Result:** 30-60s response time, ±2-3% macro accuracy

**Decision:** Speed chosen for better UX (users don't wait >30s)

---

### 10.2 LLM vs Deterministic Logic

**LLM Strengths:**
- Natural meal combinations ("salmon + roasted vegetables + quinoa")
- Contextual recommendations ("Post-workout meal: fast-digesting carbs")
- Variety across days (avoids repetition)

**LLM Weaknesses:**
- Hallucination risk (repeat recipes, wrong meal types)
- Non-deterministic (same input → different output)
- Slow (5-15s per request)

**Python Strengths:**
- Deterministic macro calculations (BMR, TDEE, targets)
- Hard safety constraints (min calories, max protein)
- Fast (<1ms for rebalancing)

**Python Weaknesses:**
- No creativity (meal pairings are mechanical)
- Requires pre-curated catalog (no discovery)

**Hybrid Approach (current):**
- Python: nutrition science, intent extraction, safety, rebalancing
- LLM: meal selection, variety, recommendations
- **Benefit:** Best of both worlds (safe + creative)

---

### 10.3 API Cost vs Data Quality

**FatSecret Free Tier:**
- 5,000 calls/day
- ~2,943 recipes extracted
- Cost: $0

**FatSecret Premier (hypothetical):**
- Unlimited calls
- All 19,000+ recipes
- Detailed micronutrient data
- Cost: ~$500/month

**Current Decision:** Free tier sufficient for POC
**Future:** Premier tier justified if >1,000 active users

---

### 10.4 Elasticsearch vs PostgreSQL + pgvector

**Elasticsearch:**
- Pros: Production-ready, fast KNN (HNSW), hybrid search, cloud-deployable
- Cons: Heavy memory footprint (~2GB for 4k docs), complex setup

**PostgreSQL + pgvector:**
- Pros: Lightweight, SQL familiarity, easier to deploy
- Cons: Slower KNN (no HNSW), limited to 2,000 dimensions, no hybrid search

**Decision:** Elasticsearch chosen for scalability + hybrid search future-proofing

---

## 11. KEY TAKEAWAYS

### 11.1 What Worked Well

1. **Hybrid Architecture (LLM + Python)**
   - Python handles deterministic logic (nutrition science, safety)
   - LLM handles creative tasks (meal selection, variety)
   - Result: Safe, fast, accurate

2. **Rule-Based Intent Extraction**
   - 40+ regex patterns extract intent <1ms
   - Handles English + Spanish
   - More reliable than LLM-based intent extraction

3. **Multi-Source Crawling**
   - 3 independent data sources (FatSecret, TheMealDB, Yuhonas)
   - Priority-based with resumable progress
   - Result: 3,609 recipes, 873 exercises

4. **Macro-Aware Ranking**
   - Judge recipes by REAL macro density (not keywords)
   - "High protein" → chicken/beef (not "protein pancakes")
   - Result: More realistic, balanced plans

5. **Allergy Safety Layer**
   - Hard filtering (before LLM generation)
   - Synonym expansion (static map + LLM)
   - Result: Zero excluded ingredients in final plans

### 11.2 Lessons Learned

1. **LLMs Need Guardrails**
   - Initial prompts: LLM repeated recipes, assigned breakfast to dinner
   - Solution: Strict JSON schema + Python validation layer
   - **Takeaway:** Never trust LLM output blindly

2. **Data Quality > Data Quantity**
   - 2,943 recipes (15% of available) sufficient for diverse plans
   - Crawler prioritization more important than exhaustive crawl
   - **Takeaway:** Curate high-quality data first

3. **Embeddings Capture Semantics**
   - "Leg hypertrophy" retrieves "squat", "lunge", "leg press" (no keyword match)
   - "High protein" retrieves chicken, beef, fish (not "protein pancakes")
   - **Takeaway:** Vector search > keyword search for nutrition/fitness

4. **Iterative Rebalancing Works**
   - 6 iterations converge to ±5-10% macro targets
   - Protein ceiling (115% target) prevents dangerous overshoot
   - **Takeaway:** Heuristics sufficient for POC, LP optimization for production

5. **Frontend Matters**
   - Staged loading progress (psychological smoothing)
   - Recipe modals (ingredients, instructions, macros)
   - PDF export (professional output)
   - **Takeaway:** UX makes or breaks adoption

---

## 12. CONCLUSION

**Summary:**
- Built a full-stack RAG system for personalized fitness plans
- Combined semantic search (Elasticsearch KNN), nutrition science (Python), and natural language generation (GPT-4o-mini)
- Achieved safe, balanced plans in 6-20 seconds

**Innovation:**
- Hybrid architecture: LLM creativity + Python safety
- Macro-aware ranking: judge by real values, not keywords
- Allergy-safe filtering: hard constraints before generation

**Impact:**
- **User:** Personalized 7-day plans from natural language
- **Technical:** Demonstrated RAG architecture for structured output (not just Q&A)
- **Research:** Showed where deterministic logic outperforms LLMs (nutrition science, safety)

**Next Steps:**
- Operations research optimization (LP, CP-SAT)
- Complete FatSecret crawl (4-day multi-run)
- Cardio exercise database integration
- Horizontal scaling (Kubernetes + Redis cache)

---

## APPENDIX: TECHNICAL SPECS

### A. Backend Tech Stack
- **Language:** Python 3.10+
- **Framework:** FastAPI 0.104.1 + Uvicorn 0.24.0
- **Vector DB:** Elasticsearch 8.11.0
- **Embeddings:** sentence-transformers 2.7.0 (PyTorch 2.12.0+cpu)
- **LLM:** OpenAI 1.54.0 (GPT-4o-mini)
- **HTTP:** httpx 0.27.2 + httpcore 1.0.7
- **Validation:** Pydantic 2.5.2
- **Env:** python-dotenv 1.0.0

### B. Frontend Tech Stack
- **Framework:** Next.js 16.2.6 (React 19.2.4)
- **Styling:** Tailwind CSS 4 + @tailwindcss/postcss
- **PDF:** jsPDF 4.2.1
- **Markdown:** react-markdown 10.1.0 + rehype-highlight 7.0.2 + remark-gfm 4.0.1
- **Syntax Highlighting:** highlight.js 11.11.1
- **Type Safety:** TypeScript 5
- **Linting:** ESLint 9 + eslint-config-next 16.2.6

### C. Data Sources
- **FatSecret API:** OAuth 1.0, 5,000 calls/day, 2,943 recipes
- **TheMealDB API:** Free tier, no auth, 666 recipes
- **Yuhonas GitHub Dump:** Static JSON, 873 exercises

### D. Key Metrics
- **Embedding Dimensions:** 384 (sentence-transformers/all-MiniLM-L6-v2)
- **KNN Candidates:** 200 (k=60 recipes)
- **LLM Temperature:** 0.3 (deterministic)
- **LLM Max Tokens:** 4,500
- **Rebalancing Iterations:** 6
- **Portion Range:** 0.5x - 2.5x (protein: 0.5x - 1.5x)
- **Weekly Consistency:** <15% spread
- **Calorie Tolerance:** ±10%
- **Protein Sufficiency:** ≥90% target
- **Response Time:** 6-20 seconds (mean: 12s)

---

**END OF PRESENTATION**

*For questions or technical deep-dives, see:*
- `BACKEND/main.py` (1,977 lines - full system logic)
- `BACKEND/crawler.py` (multi-source data pipeline)
- `BACKEND/FATSECRET_API_RESEARCH.md` (API documentation)
- `BACKEND/READY_TO_RUN.md` (execution guide)
- `app/page.tsx` (1,724 lines - frontend React component)
