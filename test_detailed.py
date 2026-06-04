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
        
        print(f"\n📊 USER PROFILE:")
        print(f"   Age: {profile.get('age')} years")
        print(f"   Sex: {profile.get('sex')}")
        print(f"   Weight: {profile.get('weight_kg')} kg")
        print(f"   Height: {profile.get('height_cm')} cm")
        print(f"   BMI: {profile.get('bmi')}")
        print(f"   Activity: {profile.get('activity_level')}")
        
        print(f"\n📈 NUTRITION SUMMARY:")
        nutrition = plan['nutrition_summary']
        print(f"   Avg Daily Calories: {nutrition['avg_daily_calories']} kcal")
        print(f"   Avg Daily Protein: {nutrition['avg_daily_protein_g']}g")
        print(f"   Avg Daily Carbs: {nutrition['avg_daily_carbs_g']}g")
        print(f"   Avg Daily Fats: {nutrition['avg_daily_fats_g']}g")
        
        print(f"\n📊 MACRO BARS:")
        for bar in plan.get('macro_bars', []):
            print(f"   {bar['label']}: {bar['value']} {bar['unit']}")
        
        safety_notes = plan.get('ai_recommendations', {}).get('safety_notes', [])
        if safety_notes:
            print(f"\n🛡️ SAFETY NOTES ({len(safety_notes)}):")
            for note in safety_notes:
                print(f"   - {note}")
        
        print(f"\n📦 Resources:")
        print(f"   Meals: {len(plan['meal_options'])}")
        print(f"   Snacks: {len(plan['snack_options'])}")
        print(f"   Exercises: {len(plan['workout_options'])}")
        
        print(f"\n📋 Plan:")
        print(f"   Title: {plan['plan_summary']['title']}")
        print(f"   Goal: {plan['plan_summary']['goal_detected']}")
        print(f"   Difficulty: {plan['plan_summary']['difficulty_level']}")
        
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)

# Run tests
print("Testing Clean API (no targets exposed)...")
test_payload(payload1, "Normal muscle gain goal")
test_payload(payload2, "Extreme crash diet request")

