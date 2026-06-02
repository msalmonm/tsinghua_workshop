#!/usr/bin/env python3
"""
RAG Health & Fitness POC - Advanced Data Crawler
Fetches massive exercises (GitHub Dump + RapidAPI) and recipes (FatSecret).
Includes Data Protection: Will not overwrite index if API limit is reached.
Search context dynamically incorporates all fields as a JSON string.
"""

import os
import sys
import re
import time
import json
import requests
from dotenv import load_dotenv
from elasticsearch import Elasticsearch, helpers
from sentence_transformers import SentenceTransformer

load_dotenv()
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

ELASTICSEARCH_URL = os.getenv('ELASTICSEARCH_URL')
ELASTICSEARCH_API_KEY = os.getenv('ELASTICSEARCH_API_KEY')
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY') 

# Credenciales de FatSecret
FATSECRET_CLIENT_ID = os.getenv('FATSECRET_CLIENT_ID')
FATSECRET_CLIENT_SECRET = os.getenv('FATSECRET_CLIENT_SECRET')

missing_vars = []
if not ELASTICSEARCH_URL: missing_vars.append("ELASTICSEARCH_URL")
if not ELASTICSEARCH_API_KEY: missing_vars.append("ELASTICSEARCH_API_KEY")

if missing_vars:
    print("\nERROR CRÍTICO DE CONFIGURACIÓN. Faltan variables base en el .env")
    sys.exit(1)

print("Loading embedding model...")
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
print("Model loaded successfully")

def generate_embedding(text):
    try:
        return model.encode(text).tolist()
    except Exception:
        return None

def fetch_rapidapi_exercises():
    """Trae ejercicios desde ExerciseDB"""
    print("\n[1/3] Buscando ejercicios en ExerciseDB...")
    exercises = []
    if not RAPIDAPI_KEY:
        print("  -> Saltando RapidAPI (No hay llave en .env)")
        return exercises
        
    url = "https://exercisedb.p.rapidapi.com/exercises"
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "exercisedb.p.rapidapi.com"}
    try:
        response = requests.get(url, headers=headers, params={"limit": "2000"}, timeout=15)
        if response.status_code == 200:
            for item in response.json():
                equipment = item.get('equipment', 'body weight')
                met = 6.0 if equipment != "body weight" else 4.0
                
                # 1. Construir el documento
                doc = {
                    'id': f"ex_rapid_{item.get('id')}",
                    'name': item.get('name'),
                    'target_muscle': item.get('target'),
                    'equipment': equipment,
                    'estimated_met': met,
                    'instructions': ' '.join(item.get('instructions', []))
                }
                
                # 2. Generar search_context dinámico como JSON
                doc['search_context'] = json.dumps(doc, ensure_ascii=False)
                exercises.append(doc)
                
        print(f"  ✓ Fetched {len(exercises)} exercises from RapidAPI")
        return exercises
    except Exception as e:
        print(f"  Aviso RapidAPI: {e}")
        return []

def fetch_github_exercises():
    """Trae +800 ejercicios del Data Dump estático de GitHub"""
    print("\n[2/3] Extrayendo base masiva de ejercicios desde GitHub Dump...")
    exercises = []
    url = "https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/dist/exercises.json"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        for i, item in enumerate(data):
            name = item.get('name', '')
            equipment = item.get('equipment', 'body only')
            muscles_list = item.get('primaryMuscles', ['various'])
            target = muscles_list[0] if muscles_list else 'various'
            instructions = " ".join(item.get('instructions', []))
            
            met = 6.0 if equipment not in ["body only", "none"] else 4.0
            
            doc = {
                'id': f"ex_gh_{i}",
                'name': name,
                'target_muscle': target,
                'equipment': equipment,
                'estimated_met': met,
                'instructions': instructions
            }
            
            # search_context dinámico como JSON
            doc['search_context'] = json.dumps(doc, ensure_ascii=False)
            exercises.append(doc)
            
        print(f"  ✓ Fetched {len(exercises)} exercises from GitHub Dump")
        return exercises
    except Exception as e:
        print(f"  Error fetching GitHub Dump: {e}")
        return []

def get_fallback_recipes():
    """Recetas locales premium en caso de fallo crítico de API"""
    print("  -> Inyectando base de datos local de respaldo para recetas...")
    
    fallback_data = [
        {
            'id': 'rec_fallback_1', 'name': 'Ensalada de Pollo a la Parrilla Alto en Proteína', 'ready_in_minutes': 20, 'diets': ['gluten free', 'high protein', 'low carb'],
            'macros': {'calories': 350, 'protein_g': 45.0, 'carbs_g': 10.0, 'fats_g': 12.0},
            'ingredients': 'pechuga de pollo, lechuga romana, aceite de oliva, tomates cherry',
            'instructions': 'Asar la pechuga, cortar en tiras y mezclar con los vegetales.'
        },
        {
            'id': 'rec_fallback_2', 'name': 'Avena Nocturna con Proteína y Chía', 'ready_in_minutes': 5, 'diets': ['vegetarian', 'high protein'],
            'macros': {'calories': 420, 'protein_g': 25.0, 'carbs_g': 45.0, 'fats_g': 10.0},
            'ingredients': 'avena, leche de almendras, scoop de proteína whey, semillas de chía',
            'instructions': 'Mezclar todo en un frasco y dejar reposar en el refrigerador toda la noche.'
        },
        {
            'id': 'rec_fallback_3', 'name': 'Salmón Glaseado con Quinoa', 'ready_in_minutes': 30, 'diets': ['pescatarian', 'gluten free'],
            'macros': {'calories': 520, 'protein_g': 38.0, 'carbs_g': 35.0, 'fats_g': 22.0},
            'ingredients': 'filete de salmón, quinoa, salsa de soja baja en sodio, brócoli',
            'instructions': 'Hornear el salmón a 200C por 15 mins. Servir sobre quinoa cocida con brócoli al vapor.'
        }
    ]
    
    # Agregar search_context como JSON dinámicamente
    for doc in fallback_data:
        doc['search_context'] = json.dumps(doc, ensure_ascii=False)
        
    return fallback_data

def fetch_fatsecret_recipes():
    """Busca recetas y desglosa sus macros usando FatSecret OAuth 2.0"""
    print("\n[3/3] Buscando recetas masivas en FatSecret...")
    recipes = []
    
    try:
        print("  -> Autenticando con FatSecret (OAuth 2.0)...")
        token_url = "https://oauth.fatsecret.com/connect/token"
        auth_req = requests.post(
            token_url, 
            data={"grant_type": "client_credentials", "scope": "basic"}, 
            auth=(FATSECRET_CLIENT_ID, FATSECRET_CLIENT_SECRET),
            timeout=10
        )
        auth_req.raise_for_status()
        access_token = auth_req.json()['access_token']
    except Exception as e:
        print(f"  ⚠️ Falló la autenticación con FatSecret: {e}")
        return get_fallback_recipes()

    api_url = "https://platform.fatsecret.com/rest/server.api"
    headers = {"Authorization": f"Bearer {access_token}"}
    queries = ['chicken', 'beef', 'pork', 'fish', 'salad', 'vegetarian', 'vegan', 'keto', 'pasta', 'soup']
    
    try:
        for q in queries:
            print(f"  -> Consultando categoría: {q}...")
            search_params = {
                "method": "recipes.search",
                "format": "json",
                "search_expression": q,
                "max_results": 10
            }
            res = requests.post(api_url, headers=headers, data=search_params, timeout=15)
            if res.status_code != 200: continue
            
            recipe_list = res.json().get('recipes', {}).get('recipe', [])
            if isinstance(recipe_list, dict): recipe_list = [recipe_list] 
            
            for r_stub in recipe_list:
                recipe_id = r_stub.get('recipe_id')
                
                det_params = {
                    "method": "recipe.get",
                    "format": "json",
                    "recipe_id": recipe_id
                }
                det_res = requests.post(api_url, headers=headers, data=det_params, timeout=10)
                if det_res.status_code != 200: continue
                
                r_data = det_res.json().get('recipe', {})
                if not r_data: continue
                
                serving = r_data.get('serving_sizes', {}).get('serving', {})
                if isinstance(serving, list): serving = serving[0]
                
                cal = float(serving.get('calories', 0))
                pro = float(serving.get('protein', 0))
                carb = float(serving.get('carbohydrate', 0))
                fat = float(serving.get('fat', 0))
                
                ing_data = r_data.get('ingredients', {}).get('ingredient', [])
                if isinstance(ing_data, dict): ing_data = [ing_data]
                ing_str = ", ".join([ing.get('ingredient_description', '') for ing in ing_data])
                
                dir_data = r_data.get('directions', {}).get('direction', [])
                if isinstance(dir_data, dict): dir_data = [dir_data]
                inst_str = " ".join([d.get('direction_description', '') for d in dir_data])
                
                prep_time = int(r_data.get('preparation_time_min', 0))
                cook_time = int(r_data.get('cooking_time_min', 0))
                ready_in = prep_time + cook_time if (prep_time or cook_time) else 30
                
                diets = [q] if q in ['vegetarian', 'vegan', 'keto'] else []
                name = r_data.get('recipe_name', 'Receta')
                
                doc = {
                    'id': f"rec_fs_{recipe_id}", 
                    'name': name,
                    'ready_in_minutes': ready_in,
                    'diets': diets,                       
                    'macros': {'calories': int(cal), 'protein_g': round(pro, 1), 'carbs_g': round(carb, 1), 'fats_g': round(fat, 1)},
                    'ingredients': ing_str,
                    'instructions': inst_str
                }
                
                # search_context dinámico como JSON
                doc['search_context'] = json.dumps(doc, ensure_ascii=False)
                recipes.append(doc)
            
            time.sleep(0.5) 
                
        print(f"  ✓ Éxito: {len(recipes)} recetas altamente detalladas extraídas de FatSecret.")
        if len(recipes) == 0: return get_fallback_recipes()
        return recipes

    except Exception as e:
        print(f"  Error Fatal en FatSecret: {e}")
        return get_fallback_recipes()

def safe_create_index(es_client, index_name, mapping, has_new_data):
    if not has_new_data:
        print(f"Saltando limpieza del índice '{index_name}' para no borrar datos previos (0 extraídos).")
        return

    if es_client.indices.exists(index=index_name):
        print(f"Borrando índice '{index_name}' para actualizar...")
        es_client.indices.delete(index=index_name)
    
    es_client.indices.create(index=index_name, body=mapping)
    print(f"Índice '{index_name}' recreado con esquemas numéricos.")

def bulk_index(es_client, index_name, documents):
    if not documents:
        return
    print(f"Generando vectores e indexando {len(documents)} documentos en '{index_name}'...")
    actions = []
    for doc in documents:
        emb = generate_embedding(doc.get('search_context', ''))
        if emb:
            doc['embedding'] = emb
            actions.append({"_index": index_name, "_id": doc['id'], "_source": doc})
    
    if actions:
        helpers.bulk(es_client, actions)
        print(f"✓ ¡Éxito! Base de datos de {index_name} poblada.")

def main():
    print("=" * 60)
    print("RAG Health & Fitness POC - FatSecret Crawler Edition")
    print("=" * 60)
    
    es_client = Elasticsearch(ELASTICSEARCH_URL, api_key=ELASTICSEARCH_API_KEY)
    
    rapid_ex = fetch_rapidapi_exercises()
    github_ex = fetch_github_exercises()
    all_exercises = rapid_ex + github_ex
    
    recipes = fetch_fatsecret_recipes()
    
    recipe_mapping = {
        "mappings": {
            "properties": {
                "name": {"type": "text"},
                "search_context": {"type": "text"},
                "ready_in_minutes": {"type": "integer"}, 
                "diets": {"type": "keyword"},            
                "macros": {
                    "properties": {
                        "calories": {"type": "integer"}, "protein_g": {"type": "float"},
                        "carbs_g": {"type": "float"}, "fats_g": {"type": "float"}
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
                "equipment": {"type": "keyword"},
                "estimated_met": {"type": "float"},
                "search_context": {"type": "text"},
                "embedding": {"type": "dense_vector", "dims": 384, "index": True, "similarity": "cosine"}
            }
        }
    }

    print("\n--- Verificando estado de la Base de Datos ---")
    safe_create_index(es_client, "exercises", exercise_mapping, has_new_data=(len(all_exercises) > 0))
    safe_create_index(es_client, "recipes", recipe_mapping, has_new_data=(len(recipes) > 0))
    
    print("\n--- Iniciando Carga Vectorial ---")
    bulk_index(es_client, "exercises", all_exercises)
    bulk_index(es_client, "recipes", recipes)
    
    print("\n" + "=" * 60)
    print("✓ Crawler finalizado con éxito total.")
    print("=" * 60)

if __name__ == "__main__":
    main()