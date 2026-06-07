#!/usr/bin/env python3
"""
Direct test of main.py functionality without requiring the server to be running
Tests the recommendation logic by directly calling the function
"""
import os
import sys
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the required components
from main import (
    UserProfile, QueryRequest, get_recommendation,
    calculate_bmr, calculate_tdee, get_activity_factor,
    extract_intent, classify_goal
)

print("=" * 80)
print("Direct Test of main.py Recommendation Logic")
print("=" * 80)

# Test cases
test_cases = [
    {
        "name": "Weight Loss - Chest Focus",
        "query": "I want to lose weight and focus on chest exercises, 4 days per week training plan",
        "profile": {
            "age": 28,
            "sex": "male",
            "weight_kg": 85.0,
            "height_cm": 175.0,
            "activity_level": "moderately_active"
        }
    },
    {
        "name": "Muscle Gain - Legs Focus",
        "query": "Build muscle with focus on legs, 5 training days per week, high protein diet",
        "profile": {
            "age": 25,
            "sex": "female",
            "weight_kg": 62.0,
            "height_cm": 165.0,
            "activity_level": "very_active"
        }
    },
    {
        "name": "Maintenance - Full Body",
        "query": "Maintain current weight with full body workouts, 3 days per week, vegetarian diet",
        "profile": {
            "age": 35,
            "sex": "male",
            "weight_kg": 75.0,
            "height_cm": 180.0,
            "activity_level": "lightly_active"
        }
    }
]

results = []

for i, test_case in enumerate(test_cases, 1):
    print(f"\n[{i}/3] Testing: {test_case['name']}")
    print(f"Query: {test_case['query']}")
    
    try:
        # Test intent extraction first
        print("  -> Extracting intent...")
        intent = extract_intent(test_case["query"])
        print(f"     Fitness Goal: {intent['fitness_goal']}")
        print(f"     Target Body Parts: {intent['target_body_parts']}")
        print(f"     Training Frequency: {intent['training_frequency_per_week']}")
        print(f"     Dietary Restrictions: {intent['dietary_restrictions']}")
        
        # Test nutrition calculations
        print("  -> Calculating nutrition targets...")
        profile = test_case['profile']
        bmr = calculate_bmr(profile['weight_kg'], profile['height_cm'], profile['age'], profile['sex'])
        activity_factor = get_activity_factor(profile['activity_level'])
        tdee = calculate_tdee(bmr, activity_factor)
        goal_type, calorie_adj = classify_goal(test_case['query'])
        print(f"     BMR: {bmr} kcal")
        print(f"     TDEE: {tdee} kcal")
        print(f"     Goal: {goal_type} ({calorie_adj:+.0%})")
        
        # Create request objects
        print("  -> Creating full recommendation...")
        user_profile = UserProfile(**profile)
        request = QueryRequest(query=test_case["query"], user_profile=user_profile)
        
        # Call the recommendation endpoint
        print("  -> Calling get_recommendation...")
        response = get_recommendation(request)
        print(f"     Response type: {type(response)}")
        print(f"     Response keys: {response.keys() if isinstance(response, dict) else 'N/A'}")
        
        # FastAPI returns a RecommendationResponse model, need to convert to dict
        if hasattr(response, 'model_dump'):
            response = response.model_dump()
        elif hasattr(response, 'dict'):
            response = response.dict()
        
        # Extract key data - response is a dict with 'response', 'plan', 'raw_data' keys
        plan = response['plan']
        plan_summary = plan.get('plan_summary', {})
        nutrition_summary = plan.get('nutrition_summary', {})
        weekly_calendar = plan.get('weekly_calendar', [])
        
        print(f"  ✓ SUCCESS")
        print(f"     Plan Title: {plan_summary.get('title', 'N/A')}")
        print(f"     Goal Detected: {plan_summary.get('goal_detected', 'N/A')}")
        print(f"     Days Generated: {len(weekly_calendar)}")
        print(f"     Avg Daily Calories: {nutrition_summary.get('avg_daily_calories', 'N/A')} kcal")
        print(f"     Avg Daily Protein: {nutrition_summary.get('avg_daily_protein_g', 'N/A')} g")
        print(f"     Workout Options: {len(plan.get('workout_options', []))}")
        print(f"     Recipe Options: {len(plan.get('meal_options', []))}")
        
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
output_file = "response.json"
print(f"\n{'=' * 80}")
print(f"Saving results to {output_file}...")

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"✓ Results saved to {output_file}")

# Summary
print(f"\n{'=' * 80}")
print("SUMMARY")
print(f"{'=' * 80}")
successful = sum(1 for r in results if r['status'] == 'success')
print(f"Total tests: {len(results)}")
print(f"Successful: {successful}")
print(f"Failed: {len(results) - successful}")
print(f"{'=' * 80}")
