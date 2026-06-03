#!/usr/bin/env python3
"""
RAG Health & Fitness POC - Lean Enterprise Crawler (TRUNCATE & LOAD)
Fuentes Activas: Yuhonas GitHub Dump (Ejercicios), TheMealDB (Recetas), FatSecret (Recetas Deep Extract).
Características: Código limpio, sin hardcodeos/alucinaciones, reinicio de base de datos total.
"""

import os
import sys
import time
import json
import string
import requests
from dotenv import load_dotenv
from elasticsearch import Elasticsearch, helpers
from sentence_transformers import SentenceTransformer

load_dotenv()
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
os.environ['HF_HUB_DISABLE_HTTP2'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'

ELASTICSEARCH_URL = os.getenv('ELASTICSEARCH_URL')
ELASTICSEARCH_API_KEY = os.getenv('ELASTICSEARCH_API_KEY')

# Credenciales de FatSecret
FATSECRET_CLIENT_ID = os.getenv('FATSECRET_CLIENT_ID', '').strip()
FATSECRET_CLIENT_SECRET = os.getenv('FATSECRET_CLIENT_SECRET', '').strip()

missing_vars = []
if not ELASTICSEARCH_URL: missing_vars.append("ELASTICSEARCH_URL")
if not ELASTICSEARCH_API_KEY: missing_vars.append("ELASTICSEARCH_API_KEY")

if missing_vars:
    print("\nERROR CRÍTICO DE CONFIGURACIÓN. Faltan variables base en el .env")
    sys.exit(1)

print("Cargando modelo de embeddings (Modo Offline/Estable)...")
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
print("Modelo cargado exitosamente.")

def generate_embedding(text):
    try:
        return model.encode(text).tolist()
    except Exception:
        return None

# ====================================================================
# EJERCICIOS
# ====================================================================

def fetch_github_yuhonas_dump():
    print("\n[1/3] Extrayendo ejercicios desde Yuhonas GitHub Dump...")
    exercises = []
    url = "https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/dist/exercises.json"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        for i, item in enumerate(data):
            equipment = item.get('equipment', 'body only')
            muscles_list = item.get('primaryMuscles', ['various'])
            target = muscles_list[0] if muscles_list else 'various'
            
            doc = {
                'id': f"ex_gh_{i}",
                'name': item.get('name', ''),
                'target_muscle': target,
                'secondary_muscles': item.get('secondaryMuscles', []),
                'body_parts': [],
                'equipment': equipment,
                'estimated_met': 6.0 if equipment not in ["body only", "none"] else 4.0,
                'instructions': " ".join(item.get('instructions', [])),
                'gif_url': ""
            }
            doc['search_context'] = json.dumps(doc, ensure_ascii=False)
            exercises.append(doc)
            
        print(f"  ✓ Se extrajeron {len(exercises)} ejercicios.")
        return exercises
    except Exception as e:
        print(f"  ⚠️ Error fetching GitHub Dump: {e}")
        return []

# ====================================================================
# RECETAS
# ====================================================================

def fetch_mealdb_recipes():
    print("\n[2/3] Extrayendo recetas masivas desde TheMealDB (A-Z)...")
    recipes = []
    letters = list(string.ascii_lowercase)
    
    try:
        for letter in letters:
            url = f"https://www.themealdb.com/api/json/v1/1/search.php?f={letter}"
            response = requests.get(url, timeout=10)
            if response.status_code != 200: continue
                
            meals = response.json().get('meals')
            if not meals: continue
                
            for meal in meals:
                meal_id = meal.get('idMeal')
                category = meal.get('strCategory', '')
                instructions = meal.get('strInstructions', '').replace('\r\n', ' ')
                
                ingredients = []
                for i in range(1, 21):
                    ing = meal.get(f'strIngredient{i}')
                    if ing and ing.strip():
                        ingredients.append(f"{meal.get(f'strMeasure{i}')} {ing}".strip())
                ing_str = ", ".join(ingredients)
                
                diets = [category.lower()] if category else []
                if category == 'Vegetarian': diets.extend(['vegetarian', 'high fiber'])
                elif category in ['Beef', 'Chicken', 'Pork', 'Seafood']: diets.append('high protein')
                    
                doc = {
                    'id': f"rec_mealdb_{meal_id}",
                    'name': meal.get('strMeal', ''),
                    'ready_in_minutes': 30, 
                    'diets': diets,
                    'macros': { 
                        # Valores en 0 al no existir en TheMealDB (Evita alucinaciones)
                        'calories': 0, 'protein_g': 0.0, 'carbs_g': 0.0, 'fats_g': 0.0,
                        'saturated_fat_g': 0.0, 'cholesterol_mg': 0.0, 'sodium_mg': 0.0, 
                        'fiber_g': 0.0, 'sugar_g': 0.0
                    },
                    'ingredients': ing_str,
                    'instructions': instructions[:1500] 
                }
                doc['search_context'] = json.dumps(doc, ensure_ascii=False)
                recipes.append(doc)
                
            time.sleep(0.2) 
            
        print(f"  ✓ {len(recipes)} recetas extraídas de TheMealDB.")
        return recipes
    except Exception as e:
        print(f"  ⚠️ Error en TheMealDB: {e}")
        return recipes

def fetch_fatsecret_recipes():
    print("\n[3/3] Buscando recetas en FatSecret (Modo Extracción Profunda)...")
    if not FATSECRET_CLIENT_ID or not FATSECRET_CLIENT_SECRET:
        print("  ⚠️ Llaves de FatSecret faltantes en .env. Saltando...")
        return []
    
    recipes = []
    try:
        # Autenticación OAuth 2.0
        token_url = "https://oauth.fatsecret.com/connect/token"
        auth_req = requests.post(
            token_url, 
            data={"grant_type": "client_credentials"},
            auth=(FATSECRET_CLIENT_ID, FATSECRET_CLIENT_SECRET), 
            timeout=10
        )
        
        if auth_req.status_code != 200:
            print(f"  ⚠️ Error de autenticación en FatSecret: {auth_req.text}")
            return []
            
        access_token = auth_req.json()['access_token']
        print("  ✓ Autenticación en FatSecret exitosa.")
        
        api_url = "https://platform.fatsecret.com/rest/server.api"
        headers = {"Authorization": f"Bearer {access_token}"}
        queries = ['chicken', 'beef', 'pork', 'salad', 'vegetarian', 'vegan', 'pasta', 'fish', 'soup', 'keto']
        
        for q in queries:
            # max_results a 50 (Explotando tier mejorado)
            search_params = {"method": "recipes.search", "format": "json", "search_expression": q, "max_results": 50}
            res = requests.post(api_url, headers=headers, data=search_params, timeout=20)
            
            if res.status_code != 200:
                print(f"  ⚠️ HTTP Error buscando '{q}' en FatSecret: {res.text}")
                continue
            
            recipe_list = res.json().get('recipes', {}).get('recipe', [])
            if isinstance(recipe_list, dict): recipe_list = [recipe_list] 
            
            print(f"  -> Procesando lote de {len(recipe_list)} recetas para categoría '{q}'...")
            
            for r_stub in recipe_list:
                recipe_id = r_stub.get('recipe_id')
                det_res = requests.post(api_url, headers=headers, data={"method": "recipe.get", "format": "json", "recipe_id": recipe_id}, timeout=15)
                
                if det_res.status_code != 200:
                    print(f"  ⚠️ Error HTTP obteniendo detalle de receta {recipe_id}: {det_res.text}")
                    continue
                
                r_data = det_res.json().get('recipe', {})
                if not r_data: continue
                
                serving = r_data.get('serving_sizes', {}).get('serving', {})
                if isinstance(serving, list): serving = serving[0]
                
                ing_data = r_data.get('ingredients', {}).get('ingredient', [])
                if isinstance(ing_data, dict): ing_data = [ing_data]
                ing_str = ", ".join([ing.get('ingredient_description', '') for ing in ing_data])
                
                dir_data = r_data.get('directions', {}).get('direction', [])
                if isinstance(dir_data, dict): dir_data = [dir_data]
                inst_str = " ".join([d.get('direction_description', '') for d in dir_data])
                
                prep_time = int(r_data.get('preparation_time_min', 0))
                cook_time = int(r_data.get('cooking_time_min', 0))
                
                # Extracción de categorías reales de FatSecret
                categories_data = r_data.get('categories', {}).get('category', [])
                if isinstance(categories_data, dict): categories_data = [categories_data]
                api_categories = [c.get('category_name', '').lower() for c in categories_data if c.get('category_name')]
                
                diets = list(set([q] + api_categories))
                
                # Extracción de imagen
                images = r_data.get('recipe_images', {}).get('recipe_image', [])
                recipe_image = images[0] if isinstance(images, list) and images else images if isinstance(images, str) else ''
                
                doc = {
                    'id': f"rec_fs_{recipe_id}", 
                    'name': r_data.get('recipe_name', 'Receta'),
                    'recipe_description': r_data.get('recipe_description', ''),
                    'recipe_url': r_data.get('recipe_url', ''),
                    'recipe_image': recipe_image,
                    'rating': float(r_data.get('rating', 0)),
                    'ready_in_minutes': prep_time + cook_time if (prep_time or cook_time) else 30,
                    'diets': diets,                       
                    'macros': {
                        'calories': int(float(serving.get('calories', 0))), 
                        'protein_g': round(float(serving.get('protein', 0)), 1), 
                        'carbs_g': round(float(serving.get('carbohydrate', 0)), 1), 
                        'fats_g': round(float(serving.get('fat', 0)), 1),
                        'saturated_fat_g': round(float(serving.get('saturated_fat', 0)), 1),
                        'polyunsaturated_fat_g': round(float(serving.get('polyunsaturated_fat', 0)), 1),
                        'monounsaturated_fat_g': round(float(serving.get('monounsaturated_fat', 0)), 1),
                        'cholesterol_mg': round(float(serving.get('cholesterol', 0)), 1),
                        'sodium_mg': round(float(serving.get('sodium', 0)), 1),
                        'potassium_mg': round(float(serving.get('potassium', 0)), 1),
                        'fiber_g': round(float(serving.get('fiber', 0)), 1),
                        'sugar_g': round(float(serving.get('sugar', 0)), 1),
                        'vitamin_a_dv': round(float(serving.get('vitamin_a', 0)), 1),
                        'vitamin_c_dv': round(float(serving.get('vitamin_c', 0)), 1),
                        'calcium_dv': round(float(serving.get('calcium', 0)), 1),
                        'iron_dv': round(float(serving.get('iron', 0)), 1)
                    },
                    'ingredients': ing_str,
                    'instructions': inst_str
                }
                doc['search_context'] = json.dumps(doc, ensure_ascii=False)
                recipes.append(doc)
            time.sleep(0.5) 
                
        print(f"  ✓ {len(recipes)} recetas de extracción profunda obtenidas de FatSecret.")
        return recipes
    except Exception as e:
        print(f"  ⚠️ Error en la ejecución de FatSecret: {e}")
        return []

# ====================================================================
# ELASTICSEARCH (TRUNCATE & LOAD)
# ====================================================================

def truncate_and_create_index(es_client, index_name, mapping):
    """Borra el índice si existe y lo crea desde cero (Truncate and Load)"""
    if es_client.indices.exists(index=index_name):
        print(f"  [TRUNCATE] Borrando índice antiguo '{index_name}'...")
        es_client.indices.delete(index=index_name)
        
    es_client.indices.create(index=index_name, body=mapping)
    print(f"  ✓ Índice '{index_name}' creado en limpio.")

def bulk_index(es_client, index_name, documents):
    if not documents: return
    print(f"Generando vectores e indexando {len(documents)} documentos en '{index_name}'...")
    actions = []
    for doc in documents:
        emb = generate_embedding(doc.get('search_context', ''))
        if emb:
            doc['embedding'] = emb
            actions.append({
                "_op_type": "index", 
                "_index": index_name, 
                "_id": doc['id'], 
                "_source": doc
            })
    
    if actions:
        helpers.bulk(es_client, actions)
        print(f"✓ ¡Éxito! Base de datos de {index_name} poblada desde cero.")

def main():
    print("=" * 60)
    print("RAG Health & Fitness POC - TRUNCATE & LOAD Crawler")
    print("=" * 60)
    
    es_client = Elasticsearch(ELASTICSEARCH_URL, api_key=ELASTICSEARCH_API_KEY)
    
    # 1. Extraer datos
    all_exercises = fetch_github_yuhonas_dump()
    
    mealdb_recipes = fetch_mealdb_recipes()
    fatsecret_recipes = fetch_fatsecret_recipes()
    
    all_recipes_dict = {rec['id']: rec for rec in mealdb_recipes}
    for rec in fatsecret_recipes: 
        all_recipes_dict[rec['id']] = rec
    all_recipes = list(all_recipes_dict.values())
    
    # 2. Mapeos Avanzados (Soporta toda la extracción profunda de FatSecret)
    recipe_mapping = {
        "mappings": {
            "properties": {
                "name": {"type": "text"},
                "recipe_description": {"type": "text"},
                "recipe_url": {"type": "keyword"},
                "recipe_image": {"type": "keyword"},
                "rating": {"type": "float"},
                "search_context": {"type": "text"},
                "ready_in_minutes": {"type": "integer"}, 
                "diets": {"type": "keyword"},            
                "macros": {
                    "properties": {
                        "calories": {"type": "integer"}, 
                        "protein_g": {"type": "float"},
                        "carbs_g": {"type": "float"}, 
                        "fats_g": {"type": "float"},
                        "saturated_fat_g": {"type": "float"},
                        "polyunsaturated_fat_g": {"type": "float"},
                        "monounsaturated_fat_g": {"type": "float"},
                        "cholesterol_mg": {"type": "float"},
                        "sodium_mg": {"type": "float"},
                        "potassium_mg": {"type": "float"},
                        "fiber_g": {"type": "float"},
                        "sugar_g": {"type": "float"},
                        "vitamin_a_dv": {"type": "float"},
                        "vitamin_c_dv": {"type": "float"},
                        "calcium_dv": {"type": "float"},
                        "iron_dv": {"type": "float"}
                    }
                },
                "embedding": {"type": "dense_vector", "dims": 384, "index": True, "similarity": "cosine"}
            }
        }
    }
    
    exercise_mapping = {
        "mappings": {
            "properties": {
                "name": {"type": "text"},
                "target_muscle": {"type": "keyword"},
                "secondary_muscles": {"type": "keyword"},
                "body_parts": {"type": "keyword"},
                "equipment": {"type": "keyword"},
                "estimated_met": {"type": "float"},
                "gif_url": {"type": "keyword"},
                "search_context": {"type": "text"},
                "embedding": {"type": "dense_vector", "dims": 384, "index": True, "similarity": "cosine"}
            }
        }
    }

    # 3. Indexación (TRUNCATE & LOAD)
    print("\n--- Verificando estado de la Base de Datos ---")
    truncate_and_create_index(es_client, "exercises", exercise_mapping)
    truncate_and_create_index(es_client, "recipes", recipe_mapping)
    
    print("\n--- Iniciando Carga Vectorial (TRUNCATE & LOAD) ---")
    if all_exercises:
        bulk_index(es_client, "exercises", all_exercises)
    else:
        print("No hay ejercicios para indexar.")
        
    if all_recipes:
        bulk_index(es_client, "recipes", all_recipes)
    else:
        print("No hay recetas para indexar.")
    
    print("\n" + "=" * 60)
    print(f"✓ Reinicio Total finalizado. Ejercicios: {len(all_exercises)} | Recetas: {len(all_recipes)}")
    print("=" * 60)

if __name__ == "__main__":
    main()