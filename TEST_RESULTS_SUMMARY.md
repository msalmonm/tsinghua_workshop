# Test Results Summary - main.py API

## Test Execution Details

**Date**: June 7, 2026  
**Test Script**: test_direct.py  
**API Endpoint Tested**: `/api/recommend` (via direct function call)  
**Output File**: response.json

## Test Cases Executed

### Test 1: Weight Loss - Chest Focus
- **Query**: "I want to lose weight and focus on chest exercises, 4 days per week training plan"
- **User Profile**: 28y male, 85kg, 175cm, moderately active
- **Status**: ✓ SUCCESS
- **Key Results**:
  - Plan Title: Chest-Focused Weight Loss Plan
  - Goal Detected: weight loss with chest focus
  - Days Generated: 7
  - Avg Daily Calories: 2031 kcal
  - Avg Daily Protein: 123.1 g
  - Workout Options: 24 exercises
  - Recipe Options: 24 recipes

### Test 2: Muscle Gain - Legs Focus
- **Query**: "Build muscle with focus on legs, 5 training days per week, high protein diet"
- **User Profile**: 25y female, 62kg, 165cm, very active
- **Status**: ✓ SUCCESS
- **Key Results**:
  - Plan Title: High-Protein Leg Muscle Gain Plan
  - Goal Detected: muscle gain with leg focus
  - Days Generated: 7
  - Avg Daily Calories: ~1600 kcal
  - Avg Daily Protein: ~130 g
  - Workout Options: 24 exercises
  - Recipe Options: 16 recipes

### Test 3: Maintenance - Full Body
- **Query**: "Maintain current weight with full body workouts, 3 days per week, vegetarian diet"
- **User Profile**: 35y male, 75kg, 180cm, lightly active
- **Status**: ✓ SUCCESS
- **Key Results**:
  - Plan Title: Balanced Vegetarian Maintenance Plan
  - Goal Detected: Maintain current weight
  - Days Generated: 7
  - Avg Daily Calories: ~2100 kcal
  - Avg Daily Protein: ~107 g
  - Workout Options: 18 exercises
  - Recipe Options: 21 recipes

## Summary

- **Total Tests**: 3
- **Successful**: 3
- **Failed**: 0
- **Success Rate**: 100%

## Files Created

1. **test_direct.py** - Direct test script that calls main.py functions without requiring a server
2. **response.json** - Complete test results with full response data for all 3 test cases
3. **TEST_RESULTS_SUMMARY.md** - This summary document

## Response Data Structure

Each test result in response.json contains:
- `test_name`: Descriptive name of the test
- `query`: The user's original query
- `status`: Test execution status
- `response_data`: Complete recommendation response including:
  - `response`: JSON string of the complete plan
  - `plan`: Structured plan object with:
    - `plan_summary`: Title, goal, focus, difficulty level
    - `intent`: Extracted user intent (fitness goal, body parts, training frequency, dietary restrictions)
    - `user_profile_summary`: BMI, BMR, TDEE calculations
    - `nutrition_summary`: Average daily macros
    - `weekly_calendar`: 7-day meal and workout plan
    - `meal_options`: Full recipe catalog with portions
    - `workout_options`: Exercise library with instructions
    - `ai_recommendations`: Personalized tips and safety notes
  - `raw_data_summary`: Count of exercises and recipes retrieved

## Notes

- All tests successfully validated nutrition calculations (BMR, TDEE, macro targets)
- Intent extraction correctly identified fitness goals, body part focus, and dietary restrictions
- Workout plans properly distributed exercises across training days
- Meal plans incorporated dietary preferences (e.g., vegetarian filter in Test 3)
- Each plan generated complete 7-day calendars with meals and workouts

## Next Steps

To run the tests again:
```bash
python test_direct.py
```

To view the complete response data:
```bash
# View in any JSON viewer or editor
code response.json  # VS Code
# or
cat response.json | jq .  # with jq tool
```
