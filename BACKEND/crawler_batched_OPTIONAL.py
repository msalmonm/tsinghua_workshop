#!/usr/bin/env python3
"""
RAG Health & Fitness POC - Lean Enterprise Crawler (BATCHED VERSION - OPCIONAL)
Esta es una versión OPCIONAL con control de batching para no exceder límites de API.

USO:
    python crawler_batched_OPTIONAL.py --batch 0  # Día 1: términos 0-24
    python crawler_batched_OPTIONAL.py --batch 1  # Día 2: términos 25-49
    python crawler_batched_OPTIONAL.py --batch 2  # Día 3: términos 50-74
    python crawler_batched_OPTIONAL.py --batch 3  # Día 4: términos 75-99

    python crawler_batched_OPTIONAL.py --all      # Ejecutar todos (riesgo de exceder límite)
"""

import os
import sys
import time
import json
import string
import requests
import argparse
from dotenv import load_dotenv
from elasticsearch import Elasticsearch, helpers
from sentence_transformers import SentenceTransformer

load_dotenv()
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
os.environ['HF_HUB_DISABLE_HTTP2'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'

ELASTICSEARCH_URL = os.getenv('ELASTICSEARCH_URL')
ELASTICSEARCH_API_KEY = os.getenv('ELASTICSEARCH_API_KEY')
FATSECRET_CLIENT_ID = os.getenv('FATSECRET_CLIENT_ID', '').strip()
FATSECRET_CLIENT_SECRET = os.getenv('FATSECRET_CLIENT_SECRET', '').strip()

# Configuración de batching
BATCH_SIZE = 25  # Términos por batch
MAX_API_CALLS_PER_BATCH = 4500  # Límite seguro (de 5000)

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
# EJERCICIOS (sin cambios)
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
# RECETAS TheMealDB (sin cambios)
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

# ====================================================================
# RECETAS FATSECRET (VERSIÓN BATCHED)
# ====================================================================

def get_all_recipe_types(access_token):
    """Obtiene todos los tipos de recetas oficiales del API de FatSecret"""
    api_url = "https://platform.fatsecret.com/rest/server.api"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        res = requests.post(api_url, headers=headers, data={
            "method": "recipe_types.get.v2",
            "format": "json"
        }, timeout=10)
        
        if res.status_code == 200:
            data = res.json().get('recipe_types', {})
            types = data.get('recipe_types', [])
            return types if isinstance(types, list) else [types]
        return []
    except Exception as e:
        print(f"  ⚠️ Error obteniendo recipe types oficiales: {e}")
        return []

def fetch_fatsecret_recipes_batched(batch_number=None, run_all=False):
    """
    Versión batched del crawler de FatSecret.
    
    Args:
        batch_number: Número de batch (0-3) o None para ejecutar según arg
        run_all: Si True, ejecuta todos los términos (riesgo de exceder límite)
    """
    print("\n[3/3] Buscando recetas en FatSecret (Modo BATCHED - Optimizado para límites de API)...")
    
    if not FATSECRET_CLIENT_ID or not FATSECRET_CLIENT_SECRET:
        print("  ⚠️ Llaves de FatSecret faltantes en .env. Saltando...")
        return []
    
    recipes = []
    seen_ids = set()
    api_calls_count = 0
    
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
        api_calls_count += 1
        print("  ✓ Autenticación en FatSecret exitosa.")
        
        api_url = "https://platform.fatsecret.com/rest/server.api"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Obtener recipe types oficiales
        print("  -> Obteniendo tipos de recetas oficiales del API...")
        official_types = get_all_recipe_types(access_token)
        api_calls_count += 1
        
        if official_types:
            print(f"  ✓ {len(official_types)} tipos oficiales obtenidos")
        
        # Queries base expandidas
        base_queries = [
            'chicken', 'beef', 'pork', 'fish', 'salmon', 'tuna', 'shrimp', 'turkey',
            'lamb', 'duck', 'bacon', 'sausage', 'ham', 'crab', 'lobster', 'tilapia',
            'salad', 'vegetarian', 'vegan', 'pasta', 'soup', 'keto', 'low carb',
            'paleo', 'whole30', 'mediterranean', 'diabetic', 'heart healthy',
            'breakfast', 'brunch', 'lunch', 'dinner', 'snack', 'dessert', 'appetizer',
            'cake', 'cookies', 'bread', 'muffin', 'brownie', 'pie', 'cupcake',
            'pizza', 'sandwich', 'burger', 'tart', 'cheesecake',
            'slow cooker', 'instant pot', 'air fryer', 'pressure cooker',
            'crockpot', 'one pot', 'sheet pan', 'no bake', 'microwave',
            'mexican', 'italian', 'asian', 'chinese', 'thai', 'indian', 'greek',
            'french', 'japanese', 'korean', 'vietnamese', 'spanish', 'moroccan',
            'rice', 'noodles', 'quinoa', 'tofu', 'lentils', 'beans', 'chickpea',
            'potato', 'sweet potato', 'mushroom', 'spinach', 'broccoli', 'avocado',
            'casserole', 'wrap', 'taco', 'burrito', 'enchilada', 'quesadilla',
            'curry', 'stew', 'chili', 'stir fry', 'risotto', 'sushi',
            'gluten free', 'dairy free', 'nut free', 'egg free', 'soy free',
            'low sodium', 'low fat', 'high protein', 'high fiber',
            'holiday', 'thanksgiving', 'christmas', 'party', 'bbq', 'picnic',
            'smoothie', 'juice', 'beverage', 'cocktail', 'shake', 'tea', 'coffee'
        ]
        
        # Combinar y deduplicar
        all_queries = list(set(base_queries + official_types))
        
        # BATCHING: Seleccionar subset de queries
        if run_all:
            selected_queries = all_queries
            print(f"\n  ⚠️ MODO COMPLETO: Procesando TODOS los {len(all_queries)} términos")
            print(f"  ⚠️ ADVERTENCIA: Esto puede exceder el límite de 5,000 API calls/día")
        else:
            if batch_number is None:
                print("  ⚠️ Debe especificar --batch N o --all")
                return []
            
            start_idx = batch_number * BATCH_SIZE
            end_idx = start_idx + BATCH_SIZE
            selected_queries = all_queries[start_idx:end_idx]
            
            print(f"\n  ═══════════════════════════════════════════════════════")
            print(f"  📦 BATCH {batch_number + 1} de {(len(all_queries) + BATCH_SIZE - 1) // BATCH_SIZE}")
            print(f"  ═══════════════════════════════════════════════════════")
            print(f"  • Términos totales disponibles: {len(all_queries)}")
            print(f"  • Términos en este batch: {len(selected_queries)}")
            print(f"  • Rango de índices: {start_idx}-{end_idx - 1}")
            print(f"  • Límite de API calls: {MAX_API_CALLS_PER_BATCH}")
            print(f"  ═══════════════════════════════════════════════════════\n")
        
        # Extracción
        for idx, q in enumerate(selected_queries, 1):
            # Chequeo de límite de API
            if api_calls_count >= MAX_API_CALLS_PER_BATCH:
                print(f"\n  ⚠️ LÍMITE DE API ALCANZADO ({MAX_API_CALLS_PER_BATCH} calls)")
                print(f"  ⚠️ Deteniendo extracción de forma segura...")
                break
            
            page_number = 0
            max_pages = 10
            
            while page_number < max_pages:
                # Chequeo de límite antes de cada call
                if api_calls_count >= MAX_API_CALLS_PER_BATCH:
                    break
                
                search_params = {
                    "method": "recipes.search", 
                    "format": "json", 
                    "search_expression": q, 
                    "max_results": 50,
                    "page_number": page_number
                }
                
                res = requests.post(api_url, headers=headers, data=search_params, timeout=20)
                api_calls_count += 1
                
                if res.status_code != 200:
                    print(f"  ⚠️ HTTP Error buscando '{q}' página {page_number}: {res.text}")
                    break
                
                response_data = res.json().get('recipes', {})
                recipe_list = response_data.get('recipe', [])
                if isinstance(recipe_list, dict): recipe_list = [recipe_list]
                
                if not recipe_list:
                    break
                
                if page_number == 0:
                    print(f"  -> [{idx}/{len(selected_queries)}] '{q}' - Página {page_number}: {len(recipe_list)} recetas... (Calls: {api_calls_count})")
                else:
                    print(f"     ↳ Página {page_number}: {len(recipe_list)} recetas... (Calls: {api_calls_count})")
                
                for r_stub in recipe_list:
                    # Chequeo antes de cada detalle
                    if api_calls_count >= MAX_API_CALLS_PER_BATCH:
                        print(f"     ⚠️ Límite alcanzado durante detalles, saltando resto...")
                        break
                    
                    recipe_id = r_stub.get('recipe_id')
                    
                    if recipe_id in seen_ids:
                        continue
                    seen_ids.add(recipe_id)
                    
                    det_res = requests.post(api_url, headers=headers, data={
                        "method": "recipe.get", 
                        "format": "json", 
                        "recipe_id": recipe_id
                    }, timeout=15)
                    api_calls_count += 1
                    
                    if det_res.status_code != 200:
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
                    
                    categories_data = r_data.get('categories', {}).get('category', [])
                    if isinstance(categories_data, dict): categories_data = [categories_data]
                    api_categories = [c.get('category_name', '').lower() for c in categories_data if c.get('category_name')]
                    
                    diets = list(set([q] + api_categories))
                    
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
                    
                    time.sleep(0.1)
                
                if idx % 5 == 0 and page_number == 0:
                    coverage_pct = (len(seen_ids) / 19000) * 100
                    print(f"  ═══ PROGRESO: {len(seen_ids)} recetas ({coverage_pct:.1f}% cobertura) | API calls: {api_calls_count}/{MAX_API_CALLS_PER_BATCH} ═══")
                
                page_number += 1
                
                if len(recipe_list) < 50:
                    break
                
                time.sleep(0.3)
                
            time.sleep(0.5)
        
        # Resumen final
        coverage_pct = (len(seen_ids) / 19000) * 100
        print(f"\n  ═══════════════════════════════════════════════════════")
        print(f"  ✓ BATCH COMPLETADO")
        print(f"  ═══════════════════════════════════════════════════════")
        print(f"  • Recetas extraídas: {len(recipes)}")
        print(f"  • IDs únicos: {len(seen_ids)}")
        print(f"  • Cobertura: {coverage_pct:.1f}% de 19,000")
        print(f"  • API calls consumidos: {api_calls_count}")
        print(f"  • Términos procesados: {len(selected_queries)}")
        print(f"  ═══════════════════════════════════════════════════════\n")
        
        return recipes
        
    except Exception as e:
        print(f"  ⚠️ Error: {e}")
        return []

# ====================================================================
# ELASTICSEARCH (igual que original)
# ====================================================================

def create_index_if_not_exists(es_client, index_name, mapping):
    if not es_client.indices.exists(index=index_name):
        print(f"  [CREATE] Índice '{index_name}' no existe. Creando...")
        es_client.indices.create(index=index_name, body=mapping)
        print(f"  ✓ Índice '{index_name}' creado exitosamente.")
    else:
        print(f"  [UPSERT] Índice '{index_name}' ya existe. Modo actualización incremental.")

def bulk_upsert(es_client, index_name, documents):
    if not documents: return
    print(f"Generando vectores e insertando/actualizando {len(documents)} documentos en '{index_name}'...")
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
        print(f"✓ ¡Éxito! {len(actions)} documentos insertados/actualizados en '{index_name}'.")

def main():
    # Parse argumentos
    parser = argparse.ArgumentParser(description='Crawler FatSecret con batching')
    parser.add_argument('--batch', type=int, help='Número de batch (0-3)')
    parser.add_argument('--all', action='store_true', help='Ejecutar todos los términos (riesgo de exceder límite)')
    args = parser.parse_args()
    
    if args.batch is None and not args.all:
        print("\nError: Debe especificar --batch N o --all")
        print("\nEjemplos:")
        print("  python crawler_batched_OPTIONAL.py --batch 0  # Día 1")
        print("  python crawler_batched_OPTIONAL.py --batch 1  # Día 2")
        print("  python crawler_batched_OPTIONAL.py --all      # Todos (riesgo)")
        sys.exit(1)
    
    print("=" * 60)
    print("RAG Health & Fitness POC - BATCHED MODE Crawler")
    print("=" * 60)
    
    es_client = Elasticsearch(ELASTICSEARCH_URL, api_key=ELASTICSEARCH_API_KEY)
    
    # 1. Ejercicios (solo si batch 0 o --all)
    if args.batch == 0 or args.all:
        all_exercises = fetch_github_yuhonas_dump()
    else:
        all_exercises = []
        print("\n[1/3] Saltando ejercicios (ya procesados en batch 0)")
    
    # 2. TheMealDB (solo si batch 0 o --all)
    if args.batch == 0 or args.all:
        mealdb_recipes = fetch_mealdb_recipes()
    else:
        mealdb_recipes = []
        print("\n[2/3] Saltando TheMealDB (ya procesados en batch 0)")
    
    # 3. FatSecret (batched)
    fatsecret_recipes = fetch_fatsecret_recipes_batched(
        batch_number=args.batch if not args.all else None,
        run_all=args.all
    )
    
    all_recipes_dict = {rec['id']: rec for rec in mealdb_recipes}
    for rec in fatsecret_recipes: 
        all_recipes_dict[rec['id']] = rec
    all_recipes = list(all_recipes_dict.values())
    
    # Mapeos
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

    print("\n--- Verificando estado de la Base de Datos ---")
    if args.batch == 0 or args.all:
        create_index_if_not_exists(es_client, "exercises", exercise_mapping)
    create_index_if_not_exists(es_client, "recipes", recipe_mapping)
    
    print("\n--- Iniciando Carga Vectorial (UPSERT MODE) ---")
    if all_exercises:
        bulk_upsert(es_client, "exercises", all_exercises)
        
    if all_recipes:
        bulk_upsert(es_client, "recipes", all_recipes)
    
    print("\n" + "=" * 60)
    if args.all:
        print(f"✓ Extracción COMPLETA finalizada.")
    else:
        print(f"✓ BATCH {args.batch + 1} finalizado.")
    print(f"Ejercicios: {len(all_exercises)} | Recetas: {len(all_recipes)}")
    print("=" * 60)

if __name__ == "__main__":
    main()
