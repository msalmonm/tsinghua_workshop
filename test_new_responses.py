#!/usr/bin/env python3
"""
Generar 3 nuevas respuestas con main.py actualizado
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
print("Generando 3 Nuevas Respuestas - main.py Actualizado")
print("=" * 80)

# Nuevos casos de prueba
test_cases = [
    {
        "name": "Recomposition - Back and Arms Focus",
        "query": "I want to recomp my body, focusing on back and arms, training 6 days per week, keto diet",
        "profile": {
            "age": 32,
            "sex": "male",
            "weight_kg": 90.0,
            "height_cm": 182.0,
            "activity_level": "very_active"
        }
    },
    {
        "name": "Weight Loss - Legs and Core",
        "query": "Lose weight focusing on legs and core exercises, 5 days per week, gluten-free meals",
        "profile": {
            "age": 29,
            "sex": "female",
            "weight_kg": 70.0,
            "height_cm": 168.0,
            "activity_level": "moderately_active"
        }
    },
    {
        "name": "Muscle Gain - Shoulders Focus",
        "query": "Build muscle mass with shoulder emphasis, 4 training days weekly, high protein pescatarian diet",
        "profile": {
            "age": 26,
            "sex": "male",
            "weight_kg": 72.0,
            "height_cm": 178.0,
            "activity_level": "very_active"
        }
    }
]

results = []

for i, test_case in enumerate(test_cases, 1):
    print(f"\n[{i}/3] Generando: {test_case['name']}")
    print(f"Query: {test_case['query']}")
    
    try:
        # Extraer intent
        print("  -> Extrayendo intent...")
        intent = extract_intent(test_case["query"])
        print(f"     Objetivo Fitness: {intent['fitness_goal']}")
        print(f"     Partes del Cuerpo: {intent['target_body_parts']}")
        print(f"     Frecuencia Entrenamiento: {intent['training_frequency_per_week']}")
        print(f"     Restricciones Dietéticas: {intent['dietary_restrictions']}")
        
        # Calcular nutrición
        print("  -> Calculando objetivos de nutrición...")
        profile = test_case['profile']
        bmr = calculate_bmr(profile['weight_kg'], profile['height_cm'], profile['age'], profile['sex'])
        activity_factor = get_activity_factor(profile['activity_level'])
        tdee = calculate_tdee(bmr, activity_factor)
        goal_type, calorie_adj = classify_goal(test_case['query'])
        print(f"     BMR: {bmr} kcal")
        print(f"     TDEE: {tdee} kcal")
        print(f"     Objetivo: {goal_type} ({calorie_adj:+.0%})")
        
        # Crear request
        print("  -> Generando recomendación completa...")
        user_profile = UserProfile(**profile)
        request = QueryRequest(query=test_case["query"], user_profile=user_profile)
        
        # Llamar endpoint
        response = get_recommendation(request)
        
        # Convertir a dict
        if hasattr(response, 'model_dump'):
            response = response.model_dump()
        elif hasattr(response, 'dict'):
            response = response.dict()
        
        # Extraer datos clave
        plan = response['plan']
        plan_summary = plan.get('plan_summary', {})
        nutrition_summary = plan.get('nutrition_summary', {})
        weekly_calendar = plan.get('weekly_calendar', [])
        
        print(f"  ✓ ÉXITO")
        print(f"     Título del Plan: {plan_summary.get('title', 'N/A')}")
        print(f"     Objetivo Detectado: {plan_summary.get('goal_detected', 'N/A')}")
        print(f"     Días Generados: {len(weekly_calendar)}")
        print(f"     Calorías Diarias Promedio: {nutrition_summary.get('avg_daily_calories', 'N/A')} kcal")
        print(f"     Proteína Diaria Promedio: {nutrition_summary.get('avg_daily_protein_g', 'N/A')} g")
        print(f"     Opciones de Ejercicio: {len(plan.get('workout_options', []))}")
        print(f"     Opciones de Recetas: {len(plan.get('meal_options', []))}") 
        
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

# Guardar resultados
output_file = "response_new.json"
print(f"\n{'=' * 80}")
print(f"Guardando resultados en {output_file}...")

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"✓ Resultados guardados en {output_file}")

# Resumen
print(f"\n{'=' * 80}")
print("RESUMEN")
print(f"{'=' * 80}")
successful = sum(1 for r in results if r['status'] == 'success')
print(f"Total de pruebas: {len(results)}")
print(f"Exitosas: {successful}")
print(f"Fallidas: {len(results) - successful}")
print(f"{'=' * 80}")
