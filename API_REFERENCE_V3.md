# Fitness RAG API v3.0 - Quick Reference

## Endpoint

```
POST /api/recommend
```

## Request Body

```json
{
  "query": "string (user's fitness goal in natural language)",
  "user_profile": {
    "age": "integer (years)",
    "sex": "string (male/female/m/f/hombre/mujer)",
    "weight_kg": "float (kilograms)",
    "height_cm": "float (centimeters)",
    "activity_level": "string (see options below)"
  }
}
```

### Activity Levels

| Value | Description | TDEE Multiplier |
|-------|-------------|-----------------|
| `sedentary` | Little to no exercise, desk job | 1.2 |
| `lightly_active` | Light exercise 1-3 days/week | 1.375 |
| `moderately_active` | Moderate exercise 3-5 days/week | 1.55 |
| `very_active` | Hard exercise 6-7 days/week | 1.725 |
| `extra_active` | Very hard exercise, physical job | 1.9 |

**Default:** `moderately_active`

## Response Structure

```json
{
  "plan": {
    "user_profile_summary": {
      "age": 24,
      "sex": "male",
      "weight_kg": 75.5,
      "height_cm": 178,
      "bmi": 23.83,
      "activity_level": "moderately_active",
      "bmr": 1752.5,                    // Basal Metabolic Rate
      "tdee": 2716,                     // Total Daily Energy Expenditure
      "activity_factor": 1.55,          // Activity multiplier
      "goal_type": "muscle_gain",
      "calorie_adjustment": 0.15,       // Goal-based adjustment (+15%)
      "safety_adjusted_goal": false,    // Whether safety limits were applied
      "target_calories": 3123,          // Daily calorie target
      "target_protein_g": 135,          // Daily protein target (g)
      "target_carbs_g": 432,            // Daily carbs target (g)
      "target_fats_g": 95               // Daily fats target (g)
    },
    "nutrition_summary": {
      "total_daily_calories_avg": 1978,
      "total_daily_protein_g_avg": 84.4,
      "total_daily_carbs_g_avg": 263.3,
      "total_daily_fats_g_avg": 71.9,
      "calculation_method": "python_validated"
    },
    "nutrition_validation": {
      "calories_within_range": false,
      "protein_sufficient": false,
      "warnings": [
        "Calories off target: 1978 kcal vs 3123 kcal target (-36%). Consider adjusting portion sizes.",
        "Protein below target: 84.4g vs 135g target (-37%). Add higher-protein recipes."
      ],
      "recalculated_macros": {
        "avg_daily_calories": 1978,
        "avg_daily_protein_g": 84.4,
        "avg_daily_carbs_g": 263.3,
        "avg_daily_fats_g": 71.9
      }
    },
    "macro_bars": [
      {
        "label": "Calories",
        "value": 1978,
        "unit": "kcal",
        "target": 3123,
        "percentage": 63
      },
      {
        "label": "Protein",
        "value": 84.4,
        "unit": "g",
        "target": 135,
        "percentage": 62
      }
      // ... carbs, fats
    ],
    "meal_options": [
      {
        "recipe_id": "rec_fs_12345",
        "recipe_name": "High Protein Breakfast",
        "ready_in_minutes": 15,
        "diet_tags": ["high protein", "gluten-free"],
        "base_calories": 400,
        "base_protein_g": 35,
        "base_carbs_g": 40,
        "base_fats_g": 12,
        "portion_options": [
          {"multiplier": 0.5, "calories": 200, "protein_g": 17.5, "carbs_g": 20, "fats_g": 6},
          {"multiplier": 1.0, "calories": 400, "protein_g": 35, "carbs_g": 40, "fats_g": 12},
          {"multiplier": 1.5, "calories": 600, "protein_g": 52.5, "carbs_g": 60, "fats_g": 18},
          {"multiplier": 2.0, "calories": 800, "protein_g": 70, "carbs_g": 80, "fats_g": 24}
        ],
        "ingredients": "...",
        "instructions": "..."
      }
      // ... more meals
    ],
    "snack_options": [
      // Similar structure to meal_options
    ],
    "workout_options": [
      {
        "exercise_id": "ex_gh_123",
        "name": "Barbell Squat",
        "target_muscle": "quadriceps",
        "equipment": "barbell",
        "estimated_met": 6.0,
        "instructions": "..."
      }
      // ... more exercises
    ],
    "weekly_calendar": [
      {
        "day": "Monday",
        "meals": [
          {
            "meal_type": "Breakfast",
            "recipe_indices": [0],
            "portion_multipliers": [1.5]
          },
          {
            "meal_type": "Morning Snack",
            "recipe_indices": [3],
            "portion_multipliers": [1.0]
          },
          {
            "meal_type": "Lunch",
            "recipe_indices": [5],
            "portion_multipliers": [1.0]
          },
          {
            "meal_type": "Afternoon Snack",
            "recipe_indices": [7],
            "portion_multipliers": [1.0]
          },
          {
            "meal_type": "Dinner",
            "recipe_indices": [12],
            "portion_multipliers": [1.5]
          }
        ],
        "daily_totals": {
          "calories": 2100,
          "protein_g": 140,
          "carbs_g": 250,
          "fats_g": 60
        },
        "workout": {
          "exercise_indices": [0, 1, 2, 3],
          "focus": "Legs",
          "duration_min": 45
        },
        "notes": "Focus on compound movements for maximum muscle activation."
      }
      // ... Tuesday through Sunday
    ],
    "ai_recommendations": {
      "main_tip": "Prioritize protein intake throughout the day to support muscle growth.",
      "personalized_notes": [
        "Your moderate activity level is ideal for steady muscle gain.",
        "Stay hydrated with at least 2.5 liters of water daily."
      ],
      "nutrition_tips": [
        "Aim for protein intake within 30 minutes post-workout.",
        "Spread meals evenly throughout the day to maintain energy."
      ],
      "workout_tips": [
        "Focus on progressive overload - increase weight gradually.",
        "Ensure 48 hours rest between training the same muscle group."
      ],
      "safety_notes": [
        "Always warm up before workouts to prevent injuries.",
        "Consult a healthcare provider before starting any new program."
      ]
    },
    "plan_summary": {
      "title": "7-Day Muscle Gain Meal and Workout Plan",
      "goal_detected": "muscle_gain",
      "short_summary": "A comprehensive plan focusing on high protein intake and progressive resistance training to support muscle growth.",
      "focus": "Lean muscle gain with adequate caloric surplus",
      "difficulty_level": "Intermediate"
    },
    "retrieved_data_summary": {
      "recipes_retrieved": 8,
      "meal_options_available": 5,
      "snack_options_available": 5,
      "exercises_used": 10,
      "source": "Elasticsearch k-NN (zero-macro filtered)",
      "validation_method": "python_recalculated"
    }
  }
}
```

## Goal Types & Adjustments

| Goal Type | Query Keywords | Calorie Adjustment | Protein Multiplier |
|-----------|---------------|-------------------|-------------------|
| `weight_loss` | lose, perder, bajar, fat, deficit | -20% | 2.0 g/kg |
| `recomp` | lose + gain, recomposition | -10% | 2.2 g/kg |
| `maintenance` | maintain, tone, mantener | 0% | 1.6 g/kg |
| `muscle_gain` | gain, bulk, masa, hypertrophy | +15% | 1.8 g/kg |

## Safety Minimums

| Sex | Minimum Daily Calories |
|-----|------------------------|
| Female | 1200 kcal |
| Male | 1500 kcal |

**Safety triggers:**
- Extreme phrases ("crash diet", "lose 10kg in 2 weeks")
- Deficit > 25% of TDEE
- Surplus > 20% of TDEE
- Target below safety minimums

## Validation Rules

| Metric | Validation Rule |
|--------|----------------|
| Calories | Within ±5% of target |
| Protein | At least 90% of target |
| Carbs/Fats | Calculated from recipes |

## Example Requests

### Muscle Gain (English)
```json
{
  "query": "I want to gain muscle and get stronger",
  "user_profile": {
    "age": 25,
    "sex": "male",
    "weight_kg": 80,
    "height_cm": 180,
    "activity_level": "very_active"
  }
}
```

### Weight Loss (Spanish)
```json
{
  "query": "Quiero perder peso de forma saludable",
  "user_profile": {
    "age": 30,
    "sex": "female",
    "weight_kg": 70,
    "height_cm": 165,
    "activity_level": "lightly_active"
  }
}
```

### Body Recomposition
```json
{
  "query": "I want to lose fat and gain muscle at the same time",
  "user_profile": {
    "age": 28,
    "sex": "male",
    "weight_kg": 85,
    "height_cm": 175,
    "activity_level": "moderately_active"
  }
}
```

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Invalid activity_level. Must be one of: sedentary, lightly_active, moderately_active, very_active, extra_active"
}
```

### 500 Internal Server Error
```json
{
  "detail": "OpenAI error: ..."
}
```

## BMR/TDEE Calculation Details

### BMR (Mifflin-St Jeor Equation)

**Male:**
```
BMR = 10 × weight_kg + 6.25 × height_cm - 5 × age + 5
```

**Female:**
```
BMR = 10 × weight_kg + 6.25 × height_cm - 5 × age - 161
```

### TDEE
```
TDEE = BMR × activity_factor
```

### Target Calories
```
target_calories = TDEE × (1 + goal_adjustment)
```

**With safety enforcement:**
```python
if target_calories < min_calories:
    target_calories = min_calories
    safety_adjusted_goal = True
```

## Macronutrient Distribution

### Protein
```
target_protein_g = weight_kg × protein_multiplier
```

### Fats (27.5% of calories)
```
target_fats_g = (target_calories × 0.275) / 9
```

### Carbs (remaining calories)
```
protein_calories = target_protein_g × 4
fat_calories = target_fats_g × 9
target_carbs_g = (target_calories - protein_calories - fat_calories) / 4
```

## Rate Limits

- No rate limits currently enforced
- Typical response time: 15-30 seconds
- Timeout recommended: 120 seconds

## Health Endpoint

```
GET /health
```

**Response:**
```json
{
  "status": "active",
  "message": "RAG API v2 is running (Hybrid: RAG + LLM)",
  "elasticsearch": "connected"
}
```

## Version Info

```
GET /
```

**Response:**
```json
{
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
```
