#!/usr/bin/env python3
"""
RAG Health & Fitness POC - Lean Enterprise Crawler (UPSERT MODE)
Fuentes Activas: Yuhonas GitHub Dump (Ejercicios), TheMealDB (Recetas), FatSecret (Recetas Deep Extract).
Características: Código limpio, sin hardcodeos/alucinaciones, modo incremental con upsert.
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

def load_progress():
    """Carga el progreso del crawler desde archivo"""
    progress_file = os.path.join(os.path.dirname(__file__), 'crawler_progress.json')
    if os.path.exists(progress_file):
        try:
            with open(progress_file, 'r') as f:
                return json.load(f)
        except:
            return {'processed_queries': [], 'last_run': None}
    return {'processed_queries': [], 'last_run': None}

def save_progress(processed_queries):
    """Guarda el progreso del crawler en archivo"""
    progress_file = os.path.join(os.path.dirname(__file__), 'crawler_progress.json')
    progress_data = {
        'processed_queries': processed_queries,
        'last_run': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    with open(progress_file, 'w') as f:
        json.dump(progress_data, f, indent=2)

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

def fetch_fatsecret_recipes():
    print("\n[3/3] Buscando recetas en FatSecret (Modo Extracción Profunda - Exhaustivo)...")
    if not FATSECRET_CLIENT_ID or not FATSECRET_CLIENT_SECRET:
        print("  ⚠️ Llaves de FatSecret faltantes en .env. Saltando...")
        return []
    
    recipes = []
    seen_ids = set()  # Evitar duplicados
    
    # Cargar progreso anterior
    progress = load_progress()
    processed_queries = set(progress.get('processed_queries', []))
    
    if processed_queries:
        print(f"  📂 Progreso anterior encontrado: {len(processed_queries)} términos ya procesados")
        print(f"  📅 Última ejecución: {progress.get('last_run', 'Desconocida')}")
    
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
        
        # NUEVO: Obtener recipe types oficiales del API
        print("  -> Obteniendo tipos de recetas oficiales del API...")
        official_types = get_all_recipe_types(access_token)
        if official_types:
            print(f"  ✓ {len(official_types)} tipos oficiales obtenidos: {', '.join(official_types[:5])}...")
        
        # ═══════════════════════════════════════════════════════════════
        # PRIORIZACIÓN: Categorías más útiles primero
        # ═══════════════════════════════════════════════════════════════
        
        # TIER 1: Proteínas principales (más buscadas por usuarios)
        tier1_queries = [
            'chicken', 'beef', 'salmon', 'turkey', 'shrimp', 
            'fish', 'tuna', 'pork'
        ]
        
        # TIER 2: Estilos de comida populares
        tier2_queries = [
            'salad', 'soup', 'pasta', 'breakfast', 'healthy',
            'low carb', 'high protein', 'keto'
        ]
        
        # TIER 3: Restricciones dietéticas comunes
        tier3_queries = [
            'vegetarian', 'vegan', 'gluten free', 'dairy free',
            'low fat', 'low sodium'
        ]
        
        # TIER 4: Estilos internacionales
        tier4_queries = [
            'mexican', 'italian', 'asian', 'chinese', 'thai', 
            'indian', 'greek', 'mediterranean'
        ]
        
        # TIER 5: Tipos de plato y técnicas
        tier5_queries = [
            'slow cooker', 'instant pot', 'air fryer', 'one pot',
            'casserole', 'stir fry', 'grill', 'roast'
        ]
        
        # TIER 6: Ingredientes base
        tier6_queries = [
            'rice', 'potato', 'quinoa', 'beans', 'lentils',
            'tofu', 'mushroom', 'broccoli', 'spinach'
        ]
        
        # TIER 7: Horneados y postres
        tier7_queries = [
            'cake', 'cookies', 'bread', 'muffin', 'brownie',
            'pie', 'dessert', 'pizza'
        ]
        
        # TIER 8: Adicionales
        tier8_queries = [
            'curry', 'stew', 'sandwich', 'burger', 'wrap',
            'smoothie', 'juice', 'noodles', 'taco', 'burrito'
        ]
        
        # Combinar en orden de prioridad
        base_queries = (
            tier1_queries + tier2_queries + tier3_queries + 
            tier4_queries + tier5_queries + tier6_queries + 
            tier7_queries + tier8_queries
        )
        
        # Agregar tipos oficiales al final (menor prioridad)
        all_queries = base_queries + official_types
        
        # Deduplicar manteniendo orden
        seen = set()
        ordered_queries = []
        for q in all_queries:
            q_lower = q.lower()
            if q_lower not in seen:
                seen.add(q_lower)
                ordered_queries.append(q)
        
        # Filtrar términos ya procesados
        pending_queries = [q for q in ordered_queries if q not in processed_queries]
        
        print(f"\n  ═══════════════════════════════════════════════════════")
        print(f"  🎯 MODO PRIORIZADO + REANUDABLE")
        print(f"  ═══════════════════════════════════════════════════════")
        print(f"  • Total de términos disponibles: {len(ordered_queries)}")
        print(f"  • Ya procesados: {len(processed_queries)}")
        print(f"  • Pendientes: {len(pending_queries)}")
        print(f"  • Objetivo: Maximizar cobertura de 19,000+ recetas")
        print(f"  ═══════════════════════════════════════════════════════")
        
        if not pending_queries:
            print(f"\n  ✓ ¡Todos los términos ya fueron procesados!")
            print(f"  💡 Elimina 'crawler_progress.json' para reiniciar desde cero")
            return recipes
        
        print(f"\n  🚀 INICIANDO extracción con términos priorizados...")
        print(f"  📊 Orden: Proteínas → Estilos → Dietas → Internacional → Técnicas → Ingredientes → Postres\n")
        
        for idx, q in enumerate(pending_queries, 1):
            page_number = 0
            max_pages = 7  # BALANCEADO: 7 páginas por búsqueda (350 recetas por término) - Más seguro para límite de API
            
            while page_number < max_pages:
                search_params = {
                    "method": "recipes.search", 
                    "format": "json", 
                    "search_expression": q, 
                    "max_results": 50,
                    "page_number": page_number
                }
                
                res = requests.post(api_url, headers=headers, data=search_params, timeout=20)
                
                if res.status_code != 200:
                    # Detectar si excedimos el límite de API
                    error_msg = res.text.lower()
                    if 'limit' in error_msg or 'exceeded' in error_msg or res.status_code == 429:
                        print(f"\n  ⚠️ LÍMITE DE API ALCANZADO")
                        print(f"  📊 Recetas extraídas antes del límite: {len(recipes)}")
                        print(f"  💾 Guardando progreso...")
                        save_progress(list(processed_queries))
                        print(f"  ✓ Progreso guardado en 'crawler_progress.json'")
                        print(f"\n  💡 MAÑANA: Ejecuta de nuevo 'python crawler.py' para continuar")
                        print(f"  🔄 Se reanudará desde: '{q}' (término {idx + len(processed_queries)} de {len(ordered_queries)})")
                        return recipes
                    else:
                        print(f"  ⚠️ HTTP Error buscando '{q}' página {page_number}: {res.text}")
                        break
                
                response_data = res.json().get('recipes', {})
                recipe_list = response_data.get('recipe', [])
                if isinstance(recipe_list, dict): recipe_list = [recipe_list]
                
                if not recipe_list:
                    break  # No más resultados para esta búsqueda
                
                # MEJORADO: Logging más informativo con prioridad
                if page_number == 0:
                    print(f"  -> [{idx}/{len(pending_queries)}] 🎯 '{q}' - Página {page_number}: {len(recipe_list)} recetas...")
                else:
                    print(f"     ↳ Página {page_number}: {len(recipe_list)} recetas...")
                
                for r_stub in recipe_list:
                    recipe_id = r_stub.get('recipe_id')
                    
                    # Evitar duplicados
                    if recipe_id in seen_ids:
                        continue
                    seen_ids.add(recipe_id)
                    
                    # Obtener detalle completo
                    det_res = requests.post(api_url, headers=headers, data={"method": "recipe.get", "format": "json", "recipe_id": recipe_id}, timeout=15)
                    
                    if det_res.status_code != 200:
                        # Verificar límite también en detalles
                        error_msg = det_res.text.lower()
                        if 'limit' in error_msg or 'exceeded' in error_msg or det_res.status_code == 429:
                            print(f"\n  ⚠️ LÍMITE DE API ALCANZADO (durante obtención de detalles)")
                            print(f"  📊 Recetas extraídas: {len(recipes)}")
                            print(f"  💾 Guardando progreso...")
                            save_progress(list(processed_queries))
                            print(f"  ✓ Progreso guardado en 'crawler_progress.json'")
                            print(f"\n  💡 MAÑANA: Ejecuta 'python crawler.py' para continuar")
                            print(f"  🔄 Se reanudará desde: '{q}' (término {idx + len(processed_queries)} de {len(ordered_queries)})")
                            return recipes
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
                    
                    time.sleep(0.1)  # Throttle individual recipe requests
                
                # NUEVO: Mostrar progreso de cobertura cada 5 términos
                if idx % 5 == 0:
                    coverage_pct = (len(seen_ids) / 19000) * 100
                    print(f"  ═══ PROGRESO: {len(seen_ids)} recetas únicas ({coverage_pct:.1f}% de 19,000 disponibles) ═══")
                
                page_number += 1
                
                # Detección temprana de última página
                if len(recipe_list) < 50:
                    print(f"     ↳ Última página alcanzada para '{q}' ({len(recipe_list)} < 50)")
                    break
                
                time.sleep(0.3)  # Throttle between pages
                
            # Marcar este término como procesado
            processed_queries.add(q)
            
            # Guardar progreso cada 5 términos (por si se interrumpe)
            if idx % 5 == 0:
                save_progress(list(processed_queries))
                print(f"  💾 Progreso guardado: {len(processed_queries)} términos completados")
            
            time.sleep(0.5)  # Throttle between search terms
                
        # Guardar progreso final
        save_progress(list(processed_queries))
        
        # Resumen final con estadísticas
        coverage_pct = (len(seen_ids) / 19000) * 100
        print(f"\n  ═══════════════════════════════════════════════════════")
        print(f"  ✓ EXTRACCIÓN COMPLETADA")
        print(f"  ═══════════════════════════════════════════════════════")
        print(f"  • Recetas únicas extraídas: {len(recipes)}")
        print(f"  • IDs únicos procesados: {len(seen_ids)}")
        print(f"  • Cobertura estimada: {coverage_pct:.1f}% de 19,000 disponibles")
        print(f"  • Términos procesados (esta sesión): {len(pending_queries)}")
        print(f"  • Términos procesados (total): {len(processed_queries)}")
        print(f"  • Términos restantes: {len(ordered_queries) - len(processed_queries)}")
        print(f"  💾 Progreso guardado en 'crawler_progress.json'")
        print(f"  ═══════════════════════════════════════════════════════\n")
        
        if len(processed_queries) < len(ordered_queries):
            print(f"  💡 Quedan {len(ordered_queries) - len(processed_queries)} términos pendientes")
            print(f"  🔄 Ejecuta de nuevo 'python crawler.py' mañana para continuar\n")
        else:
            print(f"  🎉 ¡COMPLETADO! Todos los términos fueron procesados")
            print(f"  💡 Para reiniciar desde cero, elimina 'crawler_progress.json'\n")
        
        return recipes
    except Exception as e:
        print(f"  ⚠️ Error en la ejecución de FatSecret: {e}")
        # Intentar guardar progreso antes de salir
        try:
            save_progress(list(processed_queries))
            print(f"  💾 Progreso guardado a pesar del error")
        except:
            pass
        return []

# ====================================================================
# ELASTICSEARCH (UPSERT MODE)
# ====================================================================

def create_index_if_not_exists(es_client, index_name, mapping):
    """Crea el índice solo si no existe (Modo Upsert)"""
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
                "_op_type": "index",  # 'index' hace upsert automático (inserta o actualiza)
                "_index": index_name, 
                "_id": doc['id'], 
                "_source": doc
            })
    
    if actions:
        helpers.bulk(es_client, actions)
        print(f"✓ ¡Éxito! {len(actions)} documentos insertados/actualizados en '{index_name}'.")

def main():
    print("=" * 60)
    print("RAG Health & Fitness POC - UPSERT MODE Crawler")
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

    # 3. Indexación (UPSERT MODE)
    print("\n--- Verificando estado de la Base de Datos ---")
    create_index_if_not_exists(es_client, "exercises", exercise_mapping)
    create_index_if_not_exists(es_client, "recipes", recipe_mapping)
    
    print("\n--- Iniciando Carga Vectorial (UPSERT MODE) ---")
    if all_exercises:
        bulk_upsert(es_client, "exercises", all_exercises)
    else:
        print("No hay ejercicios para indexar.")
        
    if all_recipes:
        bulk_upsert(es_client, "recipes", all_recipes)
    else:
        print("No hay recetas para indexar.")
    
    print("\n" + "=" * 60)
    print(f"✓ Actualización incremental finalizada. Ejercicios: {len(all_exercises)} | Recetas: {len(all_recipes)}")
    print("=" * 60)

if __name__ == "__main__":
    main()