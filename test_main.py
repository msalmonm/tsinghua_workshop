#!/usr/bin/env python3
"""
Test script for main.py API
Tests the recommendation endpoint with 3 different queries and saves responses
"""
import requests
import json
import time

API_URL = "http://localhost:8000/api/recommend"

# Test queries with different profiles
test_cases = [
    {
        "name": "Weight Loss - Chest Focus",
        "query": "I want to lose weight and focus on chest exercises, 4 days per week training plan",
        "user_profile": {
            "age": 28,
            "sex": "male",
            "weight_kg": 85,
            "height_cm": 175,
            "activity_level": "moderately_active"
        }
    },
    {
        "name": "Muscle Gain - Legs Focus",
        "query": "Build muscle with focus on legs, 5 training days per week, high protein diet",
        "user_profile": {
            "age": 25,
            "sex": "female",
            "weight_kg": 62,
            "height_cm": 165,
            "activity_level": "very_active"
        }
    },
    {
        "name": "Maintenance - Full Body",
        "query": "Maintain current weight with full body workouts, 3 days per week, vegetarian diet",
        "user_profile": {
            "age": 35,
            "sex": "male",
            "weight_kg": 75,
            "height_cm": 180,
            "activity_level": "lightly_active"
        }
    }
]

def test_api():
    print("=" * 80)
    print("Testing main.py API - /api/recommend endpoint")
    print("=" * 80)
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n[{i}/3] Testing: {test_case['name']}")
        print(f"Query: {test_case['query']}")
        
        payload = {
            "query": test_case["query"],
            "user_profile": test_case["user_profile"]
        }
        
        try:
            print("  -> Sending request...")
            start_time = time.time()
            response = requests.post(API_URL, json=payload, timeout=60)
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                print(f"  ✓ SUCCESS (took {elapsed:.2f}s)")
                data = response.json()
                
                # Extract key information for display
                plan = data.get('plan', {})
                plan_summary = plan.get('plan_summary', {})
                nutrition_summary = plan.get('nutrition_summary', {})
                weekly_calendar = plan.get('weekly_calendar', [])
                
                print(f"  - Plan Title: {plan_summary.get('title', 'N/A')}")
                print(f"  - Goal: {plan_summary.get('goal_detected', 'N/A')}")
                print(f"  - Days Generated: {len(weekly_calendar)}")
                print(f"  - Avg Daily Calories: {nutrition_summary.get('avg_daily_calories', 'N/A')} kcal")
                print(f"  - Avg Daily Protein: {nutrition_summary.get('avg_daily_protein_g', 'N/A')} g")
                
                results.append({
                    "test_name": test_case["name"],
                    "query": test_case["query"],
                    "status": "success",
                    "elapsed_seconds": round(elapsed, 2),
                    "response_data": data
                })
            else:
                print(f"  ✗ FAILED (HTTP {response.status_code})")
                print(f"  Error: {response.text}")
                results.append({
                    "test_name": test_case["name"],
                    "query": test_case["query"],
                    "status": "failed",
                    "http_status": response.status_code,
                    "error": response.text
                })
        
        except requests.exceptions.Timeout:
            print(f"  ✗ TIMEOUT (exceeded 60s)")
            results.append({
                "test_name": test_case["name"],
                "query": test_case["query"],
                "status": "timeout"
            })
        except requests.exceptions.ConnectionError:
            print(f"  ✗ CONNECTION ERROR - Is the server running?")
            results.append({
                "test_name": test_case["name"],
                "query": test_case["query"],
                "status": "connection_error",
                "error": "Cannot connect to API. Make sure the server is running with: python main.py or uvicorn main:app"
            })
        except Exception as e:
            print(f"  ✗ ERROR: {str(e)}")
            results.append({
                "test_name": test_case["name"],
                "query": test_case["query"],
                "status": "error",
                "error": str(e)
            })
        
        # Small delay between requests
        if i < len(test_cases):
            time.sleep(1)
    
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

if __name__ == "__main__":
    test_api()
