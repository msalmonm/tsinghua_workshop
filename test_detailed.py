#!/usr/bin/env python3
import requests
import json

url = "http://localhost:8001/api/recommend"

# Test case 1: Normal recomp goal
payload1 = {
    "query": "I want to gain muscle in my legs",
    "user_profile": {
        "age": 24,
        "sex": "male",
        "weight_kg": 75.5,
        "height_cm": 178,
        "activity_level": "moderately_active"
    }
}

# Test case 2: Extreme unsafe goal
payload2 = {
    "query": "I want to lose 10 kg in 2 weeks fast crash diet",
    "user_profile": {
        "age": 30,
        "sex": "female",
        "weight_kg": 70,
        "height_cm": 165,
        "activity_level": "sedentary"
    }
}

def test_payload(payload, test_name):
    print(f"\n{'='*80}")
    print(f"TEST: {test_name}")
    print(f"{'='*80}")
    print(f"Query: {payload['query']}")
    
    response = requests.post(url, json=payload, timeout=120)
    
    if response.status_code == 200:
        plan = response.json()['plan']
        profile = plan['user_profile_summary']
        
        print(f"\n📊 USER PROFILE (BMR/TDEE Method):")
        print(f"   BMR: {profile.get('bmr', 'N/A')} kcal")
        print(f"   Activity: {profile.get('activity_level', 'N/A')} (factor: {profile.get('activity_factor', 'N/A')})")
        print(f"   TDEE: {profile.get('tdee', 'N/A')} kcal")
        print(f"   Goal: {profile.get('goal_type', 'N/A')} ({profile.get('calorie_adjustment', 0):+.0%})")
        print(f"   Safety Adjusted: {profile.get('safety_adjusted_goal', False)}")
        
        print(f"\n🎯 TARGETS vs ACHIEVED:")
        nutrition = plan['nutrition_summary']
        print(f"   Calories: {nutrition['total_daily_calories_avg']} / {profile['target_calories']} kcal")
        print(f"   Protein:  {nutrition['total_daily_protein_g_avg']}g / {profile['target_protein_g']}g")
        print(f"   Carbs:    {nutrition['total_daily_carbs_g_avg']}g / {profile['target_carbs_g']}g")
        print(f"   Fats:     {nutrition['total_daily_fats_g_avg']}g / {profile['target_fats_g']}g")
        
        validation = plan.get('nutrition_validation', {})
        print(f"\n✅ VALIDATION:")
        print(f"   Calories in range: {validation.get('calories_within_range', False)}")
        print(f"   Protein sufficient: {validation.get('protein_sufficient', False)}")
        
        warnings = validation.get('warnings', [])
        if warnings:
            print(f"\n⚠️ WARNINGS ({len(warnings)}):")
            for w in warnings:
                print(f"   - {w}")
        
        safety_notes = plan.get('ai_recommendations', {}).get('safety_notes', [])
        if safety_notes:
            print(f"\n🛡️ SAFETY NOTES ({len(safety_notes)}):")
            for note in safety_notes:
                print(f"   - {note}")
        
        print(f"\n📦 Available: {len(plan['meal_options'])} meals, {len(plan['snack_options'])} snacks")
        print(f"   Title: {plan['plan_summary']['title']}")
        
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)

# Run tests
print("Testing Professional Nutrition-Tech API v3...")
test_payload(payload1, "Normal muscle gain goal with BMR/TDEE")
test_payload(payload2, "Extreme unsafe crash diet (should trigger safety)")

