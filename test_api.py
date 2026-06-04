#!/usr/bin/env python3
import requests
import json

url = "http://localhost:8001/api/recommend"
payload = {
    "query": "Quiero perder peso y ganar músculo",
    "user_profile": {
        "age": 28,
        "sex": "male",
        "weight_kg": 85,
        "height_cm": 175,
        "activity_level": "moderately_active"
    }
}

print("Sending request to API...")
print(f"URL: {url}")
print(f"Payload: {json.dumps(payload, indent=2)}")
print("\n" + "="*80 + "\n")

try:
    response = requests.post(url, json=payload, timeout=120)
    print(f"Status Code: {response.status_code}")
    print(f"\nResponse:")
    print("="*80)
    
    if response.status_code == 200:
        data = response.json()
        # Print plan summary if available
        if 'plan' in data:
            plan = data['plan']
            print("\n✓ Plan generado exitosamente!")
            print(f"\nTítulo: {plan.get('plan_summary', {}).get('title', 'N/A')}")
            print(f"Objetivo: {plan.get('plan_summary', {}).get('goal_detected', 'N/A')}")
            print(f"\nCalorías diarias promedio: {plan.get('nutrition_summary', {}).get('total_daily_calories_avg', 'N/A')}")
            print(f"Proteína diaria promedio: {plan.get('nutrition_summary', {}).get('total_daily_protein_g_avg', 'N/A')}g")
            print(f"\nOpciones disponibles:")
            print(f"  - Comidas: {len(plan.get('meal_options', []))}")
            print(f"  - Snacks: {len(plan.get('snack_options', []))}")
            print(f"\nEjercicios disponibles: {len(plan.get('workout_options', []))}")
            print(f"Días en calendario: {len(plan.get('weekly_calendar', []))}")
        else:
            print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
    else:
        print(response.text)
        
except Exception as e:
    print(f"✗ Error: {e}")
