# 🕷️ Documentación Técnica: crawler.py

## 🎯 Propósito

`crawler.py` es el sistema de extracción, transformación e indexación de datos (ETL) del proyecto RAG Health & Fitness. Implementa una estrategia **TRUNCATE & LOAD** que:
- Extrae datos de múltiples APIs públicas
- Genera embeddings vectoriales de 384 dimensiones
- Indexa documentos en Elasticsearch con búsqueda kNN
- Reinicia completamente la base de datos en cada ejecución

---

## 🏗️ Arquitectura del Módulo

### Flujo General
```
┌─────────────────────────────────────────────────┐
│  1. EXTRACCIÓN (Fetch from APIs)               │
│     - GitHub Yuhonas (~800 ejercicios)          │
│     - TheMealDB (~400 recetas)                  │
│     - FatSecret (~100-300 recetas)              │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│  2. TRANSFORMACIÓN (Data Cleaning)             │
│     - Normalización de campos                   │
│     - Creación de search_context (JSON)         │
│     - Deduplicación por ID                      │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│  3. VECTORIZACIÓN (Embeddings)                 │
│     - SentenceTransformer (384D)                │
│     - Encode search_context → vector            │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│  4. INDEXACIÓN (Elasticsearch)                 │
│     - DELETE índices existentes                 │
│     - CREATE con mappings actualizados          │
│     - BULK INSERT con vectores                  │
└─────────────────────────────────────────────────┘
```

---

## 🔧 Configuración Inicial

### Variables de Entorno Requeridas
```python
# .env
ELASTICSEARCH_URL=https://[instancia].gcp.cloud.es.io:443
ELASTICSEARCH_API_KEY=[api-key]
FATSECRET_CLIENT_ID=[client-id]  # Opcional
FATSECRET_CLIENT_SECRET=[secret]  # Opcional
```

### Configuraciones de Entorno
```python
load_dotenv()
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'      # Fix OpenMP warning
os.environ['HF_HUB_DISABLE_HTTP2'] = '1'         # Estabilidad HuggingFace
os.environ['HF_HUB_OFFLINE'] = '1'               # Modo offline (usa caché)
```

---

## 📥 Funciones de Extracción

### 1. fetch_github_yuhonas_dump()

**Propósito**: Extraer base de datos de ejercicios desde GitHub.

**URL**: `https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/dist/exercises.json`

**Datos Extraídos**:
```python
{
    'id': 'ex_gh_0',
    'name': 'Push-up',
    'target_muscle': 'chest',
    'secondary_muscles': ['triceps', 'shoulders'],
    'body_parts': [],
    'equipment': 'body only',
    'estimated_met': 4.0,  # 6.0 si usa equipo
    'instructions': 'Start in plank position...',
    'gif_url': '',
    'search_context': '{...}'  # JSON string completo
}
```

**Estimación de MET**:
- Ejercicios con equipo: `6.0` MET
- Ejercicios sin equipo (body weight): `4.0` MET

**Retorno**: `List[dict]` con ~800 ejercicios

**Manejo de Errores**:
```python
try:
    response = requests.get(url, timeout=15)
    response.raise_for_status()
except Exception as e:
    print(f"Error fetching GitHub Dump: {e}")
    return []  # Lista vacía en caso de fallo
```

---

### 2. fetch_mealdb_recipes()

**Propósito**: Extraer recetas masivas desde TheMealDB usando búsqueda alfabética.

**Estrategia**: Búsqueda A-Z (26 requests)
```python
letters = list(string.ascii_lowercase)  # ['a', 'b', ..., 'z']
for letter in letters:
    url = f"https://www.themealdb.com/api/json/v1/1/search.php?f={letter}"
```

**Datos Extraídos**:
```python
{
    'id': 'rec_mealdb_52772',
    'name': 'Teriyaki Chicken Casserole',
    'ready_in_minutes': 30,  # Estimado (no provisto por API)
    'diets': ['chicken', 'high protein'],  # Inferido de categoría
    'macros': {
        # TheMealDB NO provee macros → Todos en 0
        'calories': 0,
        'protein_g': 0.0,
        'carbs_g': 0.0,
        'fats_g': 0.0,
        # ...
    },
    'ingredients': '1 cup soy sauce, 2 chicken breasts, ...',
    'instructions': 'Preheat oven to 350°F...',
    'search_context': '{...}'
}
```

**Inferencia de Diets**:

```python
if category == 'Vegetarian':
    diets.extend(['vegetarian', 'high fiber'])
elif category in ['Beef', 'Chicken', 'Pork', 'Seafood']:
    diets.append('high protein')
```

**Rate Limiting**:
```python
time.sleep(0.2)  # 200ms entre requests
```

**Retorno**: `List[dict]` con ~400 recetas

---

### 3. fetch_fatsecret_recipes()

**Propósito**: Extraer recetas con información nutricional completa desde FatSecret API.

#### Fase 1: Autenticación OAuth 2.0
```python
token_url = "https://oauth.fatsecret.com/connect/token"
auth_req = requests.post(
    token_url,
    data={"grant_type": "client_credentials"},
    auth=(FATSECRET_CLIENT_ID, FATSECRET_CLIENT_SECRET),
    timeout=10
)
access_token = auth_req.json()['access_token']
```

#### Fase 2: Búsqueda por Categorías
```python
queries = [
    'chicken', 'beef', 'pork', 'salad', 'vegetarian',
    'vegan', 'pasta', 'fish', 'soup', 'keto'
]

for q in queries:
    search_params = {
        "method": "recipes.search",
        "format": "json",
        "search_expression": q,
        "max_results": 50  # Tier mejorado permite hasta 50
    }
    response = requests.post(api_url, headers=headers, data=search_params)
```

#### Fase 3: Extracción Profunda (Deep Extract)
Para cada receta encontrada, se obtiene el detalle completo:

```python
detail_params = {
    "method": "recipe.get",
    "format": "json",
    "recipe_id": recipe_id
}
detail_response = requests.post(api_url, headers=headers, data=detail_params)
```

**Datos Extraídos** (16 campos nutricionales):
```python
{
    'id': 'rec_fs_123456',
    'name': 'Grilled Chicken Breast',
    'recipe_description': 'Healthy high-protein meal',
    'recipe_url': 'https://www.fatsecret.com/calories-nutrition/...',
    'recipe_image': 'https://...',
    'rating': 4.5,
    'ready_in_minutes': 25,  # prep_time + cook_time
    'diets': ['chicken', 'high protein', 'low carb'],  # De categorías API
    'macros': {
        'calories': 165,
        'protein_g': 31.0,
        'carbs_g': 0.0,
        'fats_g': 3.6,
        'saturated_fat_g': 1.0,
        'polyunsaturated_fat_g': 0.8,
        'monounsaturated_fat_g': 1.2,
        'cholesterol_mg': 85.0,
        'sodium_mg': 74.0,
        'potassium_mg': 256.0,
        'fiber_g': 0.0,
        'sugar_g': 0.0,
        'vitamin_a_dv': 0.5,
        'vitamin_c_dv': 0.0,
        'calcium_dv': 1.5,
        'iron_dv': 4.2
    },
    'ingredients': '1 chicken breast (6 oz), 1 tsp olive oil, ...',
    'instructions': 'Step 1: Season chicken. Step 2: Grill...',
    'search_context': '{...}'
}
```

**Extracción de Categorías Reales**:
```python
categories_data = recipe_data.get('categories', {}).get('category', [])
if isinstance(categories_data, dict):
    categories_data = [categories_data]
api_categories = [c.get('category_name', '').lower() for c in categories_data]
```

**Rate Limiting**:
```python
time.sleep(0.5)  # 500ms entre categorías (más conservador)
```

**Retorno**: `List[dict]` con ~100-300 recetas (depende del tier de API)

---

## 🗄️ Mappings de Elasticsearch

### Mapping de Ejercicios
```python
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
            "embedding": {
                "type": "dense_vector",
                "dims": 384,
                "index": True,
                "similarity": "cosine"
            }
        }
    }
}
```

**Notas**:
- `keyword` para filtros exactos (equipo, músculos)
- `text` para búsqueda full-text
- `dense_vector` con similitud coseno para kNN

---

### Mapping de Recetas
```python
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
            "embedding": {
                "type": "dense_vector",
                "dims": 384,
                "index": True,
                "similarity": "cosine"
            }
        }
    }
}
```

**Notas**:
- Macros como `properties` anidadas (structured data)
- 16 campos nutricionales (soporta extracción profunda de FatSecret)
- `diets` como `keyword` para filtrado multi-valor

---

## 🔄 Estrategia TRUNCATE & LOAD

### Función: truncate_and_create_index()

**Propósito**: Garantizar consistencia total de datos mediante reinicio completo.

```python
def truncate_and_create_index(es_client, index_name, mapping):
    """Borra el índice si existe y lo crea desde cero"""
    
    # TRUNCATE
    if es_client.indices.exists(index=index_name):
        print(f"[TRUNCATE] Borrando índice antiguo '{index_name}'...")
        es_client.indices.delete(index=index_name)
    
    # CREATE
    es_client.indices.create(index=index_name, body=mapping)
    print(f"✓ Índice '{index_name}' creado en limpio.")
```

**Ventajas**:
- ✅ No hay datos antiguos corruptos
- ✅ Mappings siempre actualizados
- ✅ Sin problemas de deduplicación
- ✅ Elimina necesidad de UPSERT lógico

**Desventajas**:
- ⚠️ Downtime durante indexación (~5-10 min)
- ⚠️ Re-procesa todos los datos cada vez

**Alternativa (no implementada)**: Incremental Load con UPSERT

---

## 🧮 Generación de Embeddings

### Función: generate_embedding()

```python
def generate_embedding(text):
    """Convierte texto en vector de 384 dimensiones"""
    try:
        return model.encode(text).tolist()
    except Exception:
        return None
```

**Modelo**: `sentence-transformers/all-MiniLM-L6-v2`
- **Dimensiones**: 384
- **Velocidad**: ~1000 docs/segundo en CPU moderna
- **Calidad**: Excelente para búsqueda semántica general

**Input**: Campo `search_context` (JSON completo del documento)
```python
doc['search_context'] = json.dumps(doc, ensure_ascii=False)
embedding = generate_embedding(doc['search_context'])
```

**Output**: `List[float]` con 384 valores entre -1.0 y 1.0

---

## 📦 Indexación Bulk

### Función: bulk_index()

```python
def bulk_index(es_client, index_name, documents):
    """Indexa múltiples documentos eficientemente"""
    
    actions = []
    for doc in documents:
        # Generar embedding
        emb = generate_embedding(doc.get('search_context', ''))
        if emb:
            doc['embedding'] = emb
            actions.append({
                "_op_type": "index",
                "_index": index_name,
                "_id": doc['id'],
                "_source": doc
            })
    
    # Bulk insert (eficiente para miles de docs)
    if actions:
        helpers.bulk(es_client, actions)
        print(f"✓ {len(actions)} documentos indexados en '{index_name}'")
```

**Uso de `helpers.bulk()`**:
- Agrupa requests en batches
- Maneja retries automáticamente
- ~10x más rápido que inserts individuales

---

## 🔀 Deduplicación

### Estrategia: Dictionary por ID

```python
# Fusionar recetas de múltiples fuentes
all_recipes_dict = {rec['id']: rec for rec in mealdb_recipes}

# FatSecret sobrescribe TheMealDB (mayor prioridad)
for rec in fatsecret_recipes:
    all_recipes_dict[rec['id']] = rec

# Convertir a lista
all_recipes = list(all_recipes_dict.values())
```

**IDs Usados**:
- Ejercicios: `ex_gh_{index}`
- Recetas TheMealDB: `rec_mealdb_{idMeal}`
- Recetas FatSecret: `rec_fs_{recipe_id}`

**Prioridad**: FatSecret > TheMealDB (por calidad de macros)

---

## 🚀 Ejecución

### Comando
```bash
python crawler.py
```

### Output Esperado
```
============================================================
RAG Health & Fitness POC - TRUNCATE & LOAD Crawler
============================================================
Cargando modelo de embeddings (Modo Offline/Estable)...
Modelo cargado exitosamente.

[1/3] Extrayendo ejercicios desde Yuhonas GitHub Dump...
  ✓ Se extrajeron 844 ejercicios.

[2/3] Extrayendo recetas masivas desde TheMealDB (A-Z)...
  ✓ 412 recetas extraídas de TheMealDB.

[3/3] Buscando recetas en FatSecret (Modo Extracción Profunda)...
  ✓ Autenticación en FatSecret exitosa.
  -> Procesando lote de 50 recetas para categoría 'chicken'...
  -> Procesando lote de 42 recetas para categoría 'beef'...
  ...
  ✓ 187 recetas de extracción profunda obtenidas de FatSecret.

--- Verificando estado de la Base de Datos ---
  [TRUNCATE] Borrando índice antiguo 'exercises'...
  ✓ Índice 'exercises' creado en limpio.
  [TRUNCATE] Borrando índice antiguo 'recipes'...
  ✓ Índice 'recipes' creado en limpio.

--- Iniciando Carga Vectorial (TRUNCATE & LOAD) ---
Generando vectores e indexando 844 documentos en 'exercises'...
✓ ¡Éxito! Base de datos de exercises poblada desde cero.

Generando vectores e indexando 599 documentos en 'recipes'...
✓ ¡Éxito! Base de datos de recipes poblada desde cero.

============================================================
✓ Reinicio Total finalizado. Ejercicios: 844 | Recetas: 599
============================================================
```

### Tiempo de Ejecución
- Sin FatSecret: ~2-3 minutos
- Con FatSecret: ~5-10 minutos (depende del tier y rate limits)

---

## 🛡️ Manejo de Errores

### Errores HTTP
```python
try:
    response = requests.get(url, timeout=15)
    response.raise_for_status()
except requests.exceptions.Timeout:
    print("Timeout - servidor no respondió")
    return []
except requests.exceptions.HTTPError as e:
    print(f"HTTP Error {response.status_code}: {e}")
    return []
```

### Datos Malformados
```python
# Ingredientes pueden ser dict o list
ing_data = recipe_data.get('ingredients', {}).get('ingredient', [])
if isinstance(ing_data, dict):
    ing_data = [ing_data]  # Normalizar a lista
```

### Credenciales Faltantes
```python
if not FATSECRET_CLIENT_ID or not FATSECRET_CLIENT_SECRET:
    print("⚠️ Llaves de FatSecret faltantes. Saltando...")
    return []
```

---

## 📊 Estadísticas de Datos

### Ejercicios (GitHub Yuhonas)
```
Total: ~844 ejercicios
Músculos: 13 grupos principales
Equipos: body_only, dumbbells, barbell, machine, cable, etc.
MET promedio: 4.0-6.0
```

### Recetas (TheMealDB)
```
Total: ~412 recetas
Categorías: 15 (Beef, Chicken, Vegetarian, Seafood, etc.)
Macros: Todos en 0 (no disponibles)
Uso: Variedad y complemento
```

### Recetas (FatSecret)
```
Total: ~100-300 (depende del tier)
Macros: 16 campos completos
Uso: Fuente principal para cálculos nutricionales
Rating promedio: 4.2/5
```

---

## 🔮 Mejoras Futuras

### Corto Plazo
- [ ] Caché de embeddings (evitar re-generar)
- [ ] Logging estructurado (JSON logs)
- [ ] Métricas de indexación (tiempo, errores, duplicados)

### Medio Plazo
- [ ] Incremental Load (solo cambios)
- [ ] Paralelización de requests (asyncio)
- [ ] Validación de datos pre-indexación

### Largo Plazo
- [ ] Scheduler automático (cron diario)
- [ ] Monitoreo de calidad de datos
- [ ] Integración de fuentes adicionales (USDA FoodData, Edamam)

---

## 🧪 Testing

### Test Manual
```bash
# 1. Verificar conectividad
curl -X GET "$ELASTICSEARCH_URL/_cluster/health" \
  -H "Authorization: ApiKey $ELASTICSEARCH_API_KEY"

# 2. Ejecutar crawler
python crawler.py

# 3. Verificar índices
curl -X GET "$ELASTICSEARCH_URL/_cat/indices?v" \
  -H "Authorization: ApiKey $ELASTICSEARCH_API_KEY"

# 4. Buscar un documento
curl -X GET "$ELASTICSEARCH_URL/recipes/_search?q=chicken" \
  -H "Authorization: ApiKey $ELASTICSEARCH_API_KEY"
```

### Unit Test (ejemplo no implementado)
```python
import unittest

class TestCrawler(unittest.TestCase):
    def test_generate_embedding(self):
        embedding = generate_embedding("test text")
        self.assertEqual(len(embedding), 384)
        self.assertIsInstance(embedding[0], float)
    
    def test_fetch_github_yuhonas(self):
        exercises = fetch_github_yuhonas_dump()
        self.assertGreater(len(exercises), 500)
        self.assertIn('id', exercises[0])
```

---

## 📚 Referencias

### APIs Utilizadas
- [GitHub Yuhonas Exercise DB](https://github.com/yuhonas/free-exercise-db)
- [TheMealDB API](https://www.themealdb.com/api.php)
- [FatSecret Platform API](https://platform.fatsecret.com/api/Default.aspx)

### Librerías
- [elasticsearch-py](https://elasticsearch-py.readthedocs.io/)
- [sentence-transformers](https://www.sbert.net/)
- [requests](https://docs.python-requests.org/)

---

**Última actualización**: Junio 2026  
**Versión**: 2.0.0  
**Autor**: Proyecto Tsinghua Workshop
