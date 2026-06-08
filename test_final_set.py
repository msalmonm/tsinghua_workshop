#!/usr/bin/env python3
"""
Test Final Set - 3 Respuestas Adicionales con main.py
"""
import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()

from main import (
    UserProfile, QueryRequest, get_recommendation,
    calculate_bmr, calculate_tdee, get_activity_factor,
    extract_intent, classify_goal
)

print("=" * 80)
print("Test Final Set - 3 Respuestas Adicionales con main.py")
print("=" * 80)

# Tercer conjunto de casos de prueba - Totalmente diferentes
test_cases = [
    {
        "name": "Muscle Gain - Full Body with High Frequency",
        "query": "Gain muscle mass with full body training 7 days per week, dairy-free high protein diet, 3-day split",
        "profile": {
            "age": 24,
            "sex": "male",
            "weight_kg": 68.0,
            "height_cm": 172.0,
            "activity_level": "extremely_active"
        }
    },
    {
        "name": "Weight Loss - Arms and Chest",
        "query": "Lose fat focusing on arms and chest definition, 3 times per week training, low carb vegan meals",
        "profile": {
            "age": 38,
            "sex": "female",
            "weight_kg": 78.0,
            "height_cm": 170.0,
            "activity_level": "lightly_active"
        }
    },
    {
        "name": "Recomp - Cardio Focus with Strength",
        "query": "Body recomposition with emphasis on cardio and core strength, 5 days weekly, nut-free halal diet",
        "profile": {
            "age": 30,
            "sex": "male",
            "weight_kg": 82.0,
            "height_cm": 176.0,
            "activity_level": "moderately_active"
        }
    }
]

results = []

for i, test_case in enumerate(test_cases, 1):
    print(f"\n[{i}/3] Test: {test_case['name']}")
    print(f"Query: {test_case['query']}")
    
    try:
        # Intent extraction
        print("  -> Extrayendo intent...")
        intent = extract_intent(test_case["query"])
        print(f"     Objetivo: {intent['fitness_goal']}")
        print(f"     Partes Cuerpo: {intent['target_body_parts']}")
        print(f"     Frecuencia: {intent['training_frequency_per_week']} días/semana")
        print(f"     Restricciones: {intent['dietary_restrictions']}")
        
        # Nutrition calculations
        print("  -> Calculando nutrición...")
        profile = test_case['profile']
        bmr = calculate_bmr(profile['weight_kg'], profile['height_cm'], profile['age'], profile['sex'])
        activity_factor = get_activity_factor(profile['activity_level'])
        tdee = calculate_tdee(bmr, activity_factor)
        goal_type, calorie_adj = classify_goal(test_case['query'])
        print(f"     BMR: {bmr} kcal | TDEE: {tdee} kcal | Objetivo: {goal_type}")
        
        # Create request
        print("  -> Generando plan completo...")
        user_profile = UserProfile(**profile)
        request = QueryRequest(query=test_case["query"], user_profile=user_profile)
        
        # Call endpoint
        response = get_recommendation(request)
        
        # Convert to dict
        if hasattr(response, 'model_dump'):
            response = response.model_dump()
        elif hasattr(response, 'dict'):
            response = response.dict()
        
        # Extract key data
        plan = response['plan']
        plan_summary = plan.get('plan_summary', {})
        nutrition_summary = plan.get('nutrition_summary', {})
        weekly_calendar = plan.get('weekly_calendar', [])
        
        print(f"  ✓ ÉXITO")
        print(f"     Plan: {plan_summary.get('title', 'N/A')}")
        print(f"     Días: {len(weekly_calendar)} | Calorías: {nutrition_summary.get('avg_daily_calories', 0)} kcal")
        print(f"     Proteína: {nutrition_summary.get('avg_daily_protein_g', 0)}g | Ejercicios: {len(plan.get('workout_options', []))}")
        print(f"     Recetas: {len(plan.get('meal_options', []))}")
        
        results.append({
            "test_name": test_case["name"],
            "query": test_case["query"],
            "status": "success",
            "response_data": {
                "response": response['response'],
                "plan": response['plan'],
                "raw_data_summary": {
                    "exercises_count": len(response['raw_data'].get('exercises', [])),
                    "recipes_count": len(response['raw_data'].get('recipes', []))
                }
            }
        })
        
    except Exception as e:
        print(f"  ✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        results.append({
            "test_name": test_case["name"],
            "query": test_case["query"],
            "status": "error",
            "error": str(e)
        })

# Save results
output_file = "response_final.json"
print(f"\n{'=' * 80}")
print(f"Guardando en {output_file}...")

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"✓ Guardado en {output_file}")

# Summary
print(f"\n{'=' * 80}")
print("RESUMEN")
print(f"{'=' * 80}")
successful = sum(1 for r in results if r['status'] == 'success')
print(f"Total: {len(results)} | Exitosos: {successful} | Fallidos: {len(results) - successful}")
print(f"{'=' * 80}")
