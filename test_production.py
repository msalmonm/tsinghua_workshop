#!/usr/bin/env python3
import requests
import json

url = "https://tsinghua-workshop.onrender.com/api/recommend"
payload = {
    "query": "I want to lose weight and build muscle",
    "user_profile": {
        "age": 28,
        "sex": "male",
        "weight_kg": 85,
        "height_cm": 175
    }
}

print("Testing production API on Render...")
print(f"URL: {url}")
print(f"Payload: {json.dumps(payload, indent=2)}")
print("\n" + "="*80 + "\n")

try:
    response = requests.post(url, json=payload, timeout=120)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        if 'plan' in data:
            plan = data['plan']
            print("\n✓ SUCCESS! Plan generated")
            print(f"\nTitle: {plan.get('plan_summary', {}).get('title', 'N/A')}")
            print(f"Goal: {plan.get('plan_summary', {}).get('goal_detected', 'N/A')}")
            print(f"\nDaily calories avg: {plan.get('nutrition_summary', {}).get('total_daily_calories_avg', 'N/A')}")
            print(f"Daily protein avg: {plan.get('nutrition_summary', {}).get('total_daily_protein_g_avg', 'N/A')}g")
            print(f"\nMeal options: {len(plan.get('meal_options', {}).get('breakfast', []))} breakfast, {len(plan.get('meal_options', {}).get('lunch', []))} lunch, {len(plan.get('meal_options', {}).get('dinner', []))} dinner")
            print(f"Exercises: {len(plan.get('workout_options', []))}")
            print(f"Calendar days: {len(plan.get('weekly_calendar', []))}")
            print(f"\n✓ All data looks good!")
        else:
            print(json.dumps(data, indent=2)[:500])
    else:
        print(f"\n✗ Error: {response.text}")
        
except Exception as e:
    print(f"✗ Error: {e}")
