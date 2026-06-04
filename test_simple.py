#!/usr/bin/env python3
import requests
import json

url = "http://localhost:8001/api/recommend"
payload = {
    "query": "I want to gain muscle",
    "user_profile": {
        "age": 25,
        "sex": "male",
        "weight_kg": 75,
        "height_cm": 178,
        "activity_level": "moderately_active"
    }
}

print("Probando API v3...")
try:
    response = requests.post(url, json=payload, timeout=120)
    
    if response.status_code == 200:
        data = response.json()
        
        # Mostrar estructura de la respuesta
        print("\n✓ Respuesta exitosa")
        print(f"\nClaves principales: {list(data.keys())}")
        
        if 'plan' in data:
            plan = data['plan']
            print(f"Claves del plan: {list(plan.keys())}")
            
            # Mostrar perfil de usuario
            if 'user_profile_summary' in plan:
                profile = plan['user_profile_summary']
                print(f"\n📊 USER PROFILE:")
                print(f"   BMR: {profile.get('bmr', 'N/A')} kcal")
                print(f"   TDEE: {profile.get('tdee', 'N/A')} kcal")
                print(f"   Activity: {profile.get('activity_level', 'N/A')}")
                print(f"   Goal: {profile.get('goal_type', 'N/A')}")
                print(f"   Target Calories: {profile.get('target_calories', 'N/A')} kcal")
            
            # Mostrar resumen nutricional si existe
            if 'nutrition_summary' in plan:
                print(f"\n✓ nutrition_summary existe")
            else:
                print(f"\n⚠️ nutrition_summary NO existe en la respuesta")
                
            # Mostrar validación si existe
            if 'nutrition_validation' in plan:
                validation = plan['nutrition_validation']
                print(f"\n✅ VALIDATION:")
                print(f"   Calories OK: {validation.get('calories_within_range', 'N/A')}")
                print(f"   Protein OK: {validation.get('protein_sufficient', 'N/A')}")
                warnings = validation.get('warnings', [])
                if warnings:
                    print(f"   Warnings: {len(warnings)}")
                    for w in warnings[:2]:
                        print(f"     - {w}")
        
        # Guardar respuesta completa
        with open('response_debug.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("\n💾 Respuesta completa guardada en: response_debug.json")
        
    else:
        print(f"❌ Error {response.status_code}")
        print(response.text)
        
except Exception as e:
    print(f"❌ Exception: {e}")
