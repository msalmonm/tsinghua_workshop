# FatSecret API - Investigación Exhaustiva y Plan de Optimización

## 📊 RESUMEN EJECUTIVO

**Capacidades del API de FatSecret:**
- ✅ **19,000+ recetas** con imágenes, instrucciones e información nutricional completa
- ✅ **2.3 millones de alimentos** verificados (generic, branded, supermarket, restaurant)
- ✅ **Ejercicios básicos** (limitados a tipos de ejercicio, NO incluye rutinas de gimnasio detalladas)
- ✅ **58+ países** y **26 idiomas** (requiere plan Premier)
- ✅ **Información de alergenos y preferencias dietéticas** (Premier)
- ✅ **Image Recognition & NLP** (Premier exclusivo)
- ⚠️ **Límite gratuito**: 5,000 llamadas/día, solo datos de USA

---

## 🔍 HALLAZGOS CLAVE

### 1. RECETAS - Estrategia de Extracción Máxima

#### ✅ Lo que SÍ funciona (ya implementado):
```python
# Paginación automática (max 50 resultados por página)
max_results: 50
page_number: 0, 1, 2, 3, 4...

# Búsquedas múltiples por categoría
queries = ['chicken', 'beef', 'salad', etc.]
```

#### 🚀 MEJORAS IMPLEMENTABLES:

##### A. Usar `recipe_types.get.v2` para categorías oficiales
El API tiene un endpoint que devuelve TODOS los tipos de recetas soportados:

**Endpoint:** `https://platform.fatsecret.com/rest/recipe-types/v2`

**Tipos de recetas documentados:**
- Appetizers
- Soups
- Main Dishes
- Desserts
- Salads
- Beverages
- Breakfast
- Breads
- Snacks
- Sides
- Sauces and Condiments

**Implementación sugerida:**
```python
# 1. Primero obtener todos los recipe_types oficiales
def get_all_recipe_types():
    api_url = "https://platform.fatsecret.com/rest/server.api"
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.post(api_url, headers=headers, data={
        "method": "recipe_types.get.v2",
        "format": "json"
    })
    recipe_types = res.json().get('recipe_types', {}).get('recipe_types', [])
    return recipe_types

# 2. Buscar recetas por cada tipo oficial
for recipe_type in official_recipe_types:
    search_params = {
        "method": "recipes.search",
        "format": "json",
        "search_expression": recipe_type,
        "recipe_types": recipe_type,  # Filtro adicional
        "max_results": 50,
        "page_number": page
    }
```

##### B. Filtros adicionales en `recipes.search`

**Parámetros disponibles (no documentados completamente pero válidos):**
- `search_expression`: Término de búsqueda
- `max_results`: Máximo 50 por llamada
- `page_number`: Para paginación (empieza en 0)
- `recipe_types`: Filtrar por tipo de receta (comma-separated)

##### C. Estrategia de términos de búsqueda expandida

**Categorías actuales (48):** Ya bastante completas ✅

**Categorías adicionales sugeridas:**
```python
additional_queries = [
    # Preparaciones/técnicas
    'slow cooker', 'instant pot', 'air fryer', 'pressure cooker',
    'crockpot', 'microwave', 'no bake', 'one pot',
    
    # Ocasiones
    'holiday', 'thanksgiving', 'christmas', 'party', 'picnic',
    
    # Dietas específicas
    'paleo', 'whole30', 'mediterranean', 'diabetic', 'heart healthy',
    
    # Ingredientes premium
    'quinoa', 'tofu', 'tempeh', 'lentils', 'chickpea',
    
    # Comidas específicas
    'brunch', 'appetizer', 'side dish', 'snack', 'beverage'
]
```

##### D. Búsqueda por ID ranges (técnica avanzada)

Si el API asigna IDs secuenciales, se podría intentar:
```python
# Obtener recetas por rango de IDs (si recipe_id es secuencial)
for recipe_id in range(1, 20000):  # 19,000+ recetas
    try:
        get_recipe_detail(recipe_id)
    except:
        continue
```
⚠️ **RIESGO**: Consumo masivo de API calls. Solo usar si se confirma que IDs son secuenciales.

---

### 2. EJERCICIOS - Limitaciones Críticas ⚠️

#### ❌ Lo que NO tiene FatSecret:

El API de **FatSecret NO provee rutinas de gimnasio detalladas**. Solo tiene:

**Endpoint disponible:** `exercises.get.v2`

**Tipos de ejercicios (básicos):**
```json
[
  {"exercise_id": 0, "exercise_name": "Other"},
  {"exercise_id": 1, "exercise_name": "Sleeping"},
  {"exercise_id": 2, "exercise_name": "Resting"},
  {"exercise_id": 3, "exercise_name": "Walking"},
  {"exercise_id": 4, "exercise_name": "Running"},
  // ... ejercicios generales de cardio
]
```

**Propósito:** Para tracking de calorías quemadas en diary de ejercicio del usuario.

#### ✅ SOLUCIÓN: Mantener Yuhonas GitHub Dump

El crawler actual usa `yuhonas/free-exercise-db` que SÍ provee:
- ✅ 873+ ejercicios detallados
- ✅ Músculos primarios y secundarios
- ✅ Equipamiento requerido
- ✅ Instrucciones paso a paso
- ✅ GIF animations (opcional)

**CONCLUSIÓN:** FatSecret NO reemplaza la fuente de ejercicios actual. Mantener Yuhonas.

---

### 3. ALIMENTOS (2.3M+ items) - Oportunidad Masiva 🌟

#### 🚀 NUEVO FEATURE: Agregar base de alimentos individuales

El API tiene endpoints robustos para alimentos:

**Endpoint principal:** `foods.search`

**Capacidades:**
- Búsqueda por nombre, marca, categoría
- Información nutricional completa por serving
- UPC/Barcode lookup (90%+ cobertura global)
- Food categories and sub-categories

**Implementación sugerida:**
```python
def fetch_fatsecret_foods():
    """
    Nuevo módulo para extraer alimentos individuales.
    Útil para tracking nutricional detallado.
    """
    # Categorías de alimentos comunes
    food_categories = [
        'fruits', 'vegetables', 'dairy', 'meat', 'seafood',
        'grains', 'nuts', 'seeds', 'oils', 'beverages',
        'snacks', 'condiments', 'spices'
    ]
    
    for category in food_categories:
        page = 0
        while True:
            search_params = {
                "method": "foods.search",
                "format": "json",
                "search_expression": category,
                "max_results": 50,
                "page_number": page
            }
            # ... paginación automática
```

**Ventajas:**
- Los usuarios podrían buscar alimentos individuales
- Crear recetas personalizadas
- Mejor análisis nutricional

---

## 📋 PLAN DE IMPLEMENTACIÓN

### FASE 1: Optimización de Recetas (PRIORITARIO) ⭐

**Objetivo:** Maximizar extracción hasta alcanzar las 19,000+ recetas

**Cambios en `crawler.py`:**

```python
def fetch_fatsecret_recipes_ENHANCED():
    """
    Versión mejorada con:
    1. Recipe types oficiales del API
    2. Términos de búsqueda expandidos
    3. Mejor logging de progreso
    4. Estimación de cobertura total
    """
    
    # PASO 1: Obtener recipe types oficiales
    official_types = get_all_recipe_types()
    print(f"  -> Tipos de receta oficiales: {len(official_types)}")
    
    # PASO 2: Búsquedas base (actuales + nuevas)
    base_queries = [
        # Proteínas (actuales)
        'chicken', 'beef', 'pork', 'fish', 'salmon', 'tuna', 
        'shrimp', 'turkey',
        
        # Estilos (actuales)
        'salad', 'vegetarian', 'vegan', 'pasta', 'soup', 
        'keto', 'low carb',
        
        # Comidas (actuales)
        'breakfast', 'lunch', 'dinner', 'dessert',
        
        # Horneados (actuales)
        'cake', 'cookies', 'bread', 'pizza',
        
        # NUEVOS - Técnicas de cocción
        'slow cooker', 'instant pot', 'air fryer', 'grill',
        'bake', 'roast', 'stir fry', 'one pot',
        
        # NUEVOS - Estilos internacionales
        'mexican', 'italian', 'asian', 'chinese', 'thai', 
        'indian', 'greek', 'mediterranean', 'french',
        
        # NUEVOS - Ingredientes principales
        'rice', 'quinoa', 'tofu', 'lentils', 'beans',
        
        # NUEVOS - Dietas específicas
        'paleo', 'whole30', 'gluten free', 'dairy free',
        'diabetic', 'heart healthy', 'low sodium',
        
        # NUEVOS - Tipos de plato
        'appetizer', 'side dish', 'snack', 'beverage',
        'casserole', 'wrap', 'taco', 'burrito'
    ]
    
    # PASO 3: Combinar con recipe_types oficiales
    all_search_terms = base_queries + official_types
    all_search_terms = list(set(all_search_terms))  # Remove duplicates
    
    print(f"  -> Total de términos de búsqueda: {len(all_search_terms)}")
    
    # PASO 4: Búsqueda exhaustiva con tracking
    total_unique = 0
    for idx, query in enumerate(all_search_terms, 1):
        print(f"  -> [{idx}/{len(all_search_terms)}] Buscando: {query}")
        
        page = 0
        while page < 10:  # Aumentar a 10 páginas (500 por término)
            # ... lógica de búsqueda actual
            
            # NUEVO: Tracking de progreso
            if len(recipe_list) < 50:
                print(f"     ↳ Última página alcanzada ({len(recipe_list)} recetas)")
                break
            
            page += 1
        
        # NUEVO: Estimación de cobertura
        coverage_pct = (len(seen_ids) / 19000) * 100
        print(f"  -> Progreso: {len(seen_ids)} recetas únicas ({coverage_pct:.1f}% del total)")
```

**Resultado esperado:**
- Actual: ~3,500 recetas (estimado por tu output)
- Objetivo: 15,000-19,000 recetas (80-100% cobertura)

---

### FASE 2: Agregar Foods Database (OPCIONAL)

**Solo si se necesita tracking de alimentos individuales**

```python
def fetch_fatsecret_foods():
    """
    Nuevo índice Elasticsearch: 'foods'
    Estructura similar a 'recipes' pero para alimentos individuales
    """
    # Ver implementación completa arriba
```

**Mapping de Elasticsearch para Foods:**
```python
food_mapping = {
    "mappings": {
        "properties": {
            "food_id": {"type": "keyword"},
            "food_name": {"type": "text"},
            "food_type": {"type": "keyword"},  # Generic, Brand, etc.
            "brand_name": {"type": "text"},
            "food_url": {"type": "keyword"},
            "servings": {
                "type": "nested",
                "properties": {
                    "serving_id": {"type": "keyword"},
                    "serving_description": {"type": "text"},
                    "serving_url": {"type": "keyword"},
                    "metric_serving_amount": {"type": "float"},
                    "metric_serving_unit": {"type": "keyword"},
                    "calories": {"type": "integer"},
                    "protein": {"type": "float"},
                    "carbohydrate": {"type": "float"},
                    "fat": {"type": "float"},
                    "saturated_fat": {"type": "float"},
                    "fiber": {"type": "float"},
                    "sugar": {"type": "float"},
                    "sodium": {"type": "float"}
                }
            },
            "embedding": {"type": "dense_vector", "dims": 384}
        }
    }
}
```

---

### FASE 3: Features Premium (Requiere upgrade del plan)

**Actualmente en plan gratuito:**
- ✅ 5,000 API calls/día
- ✅ Datos solo de USA
- ❌ No image recognition
- ❌ No NLP
- ❌ No localization

**Con plan Premier:**
- ✅ Unlimited API calls
- ✅ 58+ países, 26 idiomas
- ✅ Image Recognition (identificar comida en fotos)
- ✅ Natural Language Processing ("I ate 2 slices of pizza" → structured data)
- ✅ Allergen information
- ✅ High-quality food images
- ✅ Barcode scanning (90%+ cobertura)

---

## 🎯 MODIFICACIONES AL CÓDIGO

### Archivo: `crawler.py`

#### 1. Agregar función para recipe types oficiales:

```python
def get_all_recipe_types(access_token):
    """Obtiene todos los tipos de recetas oficiales del API"""
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
        print(f"  ⚠️ Error obteniendo recipe types: {e}")
        return []
```

#### 2. Expandir lista de queries:

```python
# En fetch_fatsecret_recipes(), REEMPLAZAR la lista 'queries':

# Obtener tipos oficiales
official_types = get_all_recipe_types(access_token)

# Queries base expandidas
base_queries = [
    # Proteínas
    'chicken', 'beef', 'pork', 'fish', 'salmon', 'tuna', 'shrimp', 'turkey',
    'lamb', 'duck', 'bacon', 'sausage', 'ham',
    
    # Estilos de comida
    'salad', 'vegetarian', 'vegan', 'pasta', 'soup', 'keto', 'low carb',
    'paleo', 'whole30', 'mediterranean', 'diabetic',
    
    # Comidas del día
    'breakfast', 'brunch', 'lunch', 'dinner', 'snack', 'dessert',
    
    # Horneados
    'cake', 'cookies', 'bread', 'muffin', 'brownie', 'pie',
    'pizza', 'sandwich', 'burger',
    
    # Técnicas de cocción
    'slow cooker', 'instant pot', 'air fryer', 'grill', 'bake', 
    'roast', 'stir fry', 'one pot', 'sheet pan',
    
    # Estilos internacionales
    'mexican', 'italian', 'asian', 'chinese', 'thai', 'indian',
    'greek', 'french', 'japanese', 'korean', 'vietnamese',
    
    # Ingredientes principales
    'rice', 'noodles', 'quinoa', 'tofu', 'lentils', 'beans',
    'chickpea', 'potato', 'sweet potato',
    
    # Tipos de plato
    'appetizer', 'side dish', 'casserole', 'wrap', 'taco',
    'enchilada', 'quesadilla', 'curry', 'stew'
]

# Combinar y deduplicar
queries = list(set(base_queries + official_types))
print(f"  -> Extrayendo con {len(queries)} términos de búsqueda únicos...")
```

#### 3. Aumentar páginas por búsqueda:

```python
# En fetch_fatsecret_recipes(), cambiar:
max_pages = 5  # ANTES

max_pages = 10  # DESPUÉS (permite hasta 500 recetas por término)
```

#### 4. Agregar tracking de cobertura:

```python
# Después de cada búsqueda, agregar:
if q in ['chicken', 'breakfast', 'dessert']:  # Términos comunes
    coverage_estimate = (len(seen_ids) / 19000) * 100
    print(f"  -> Cobertura estimada: {len(seen_ids)}/19,000 ({coverage_estimate:.1f}%)")
```

---

### Archivo: `main.py`

#### Mejora en priorización de FatSecret:

```python
# En search_elasticsearch(), línea ~335:
# ANTES:
if index_name == "recipes":
    fatsecret = [r for r in results if r.get("id", "").startswith("rec_fs_")]
    others = [r for r in results if not r.get("id", "").startswith("rec_fs_")]
    results = fatsecret + others

# DESPUÉS (más robusto):
if index_name == "recipes":
    # Priorizar FatSecret (data completa) > TheMealDB (data parcial)
    fatsecret = [r for r in results if r.get("id", "").startswith("rec_fs_")]
    mealdb = [r for r in results if r.get("id", "").startswith("rec_mealdb_")]
    others = [r for r in results if r not in fatsecret and r not in mealdb]
    
    # Orden: FatSecret → Otros → MealDB (último por falta de macros)
    results = fatsecret + others + mealdb
```

---

## ⚙️ CONFIGURACIÓN RECOMENDADA

### Variables de entorno (.env):

```bash
# Elasticsearch
ELASTICSEARCH_URL=your_elasticsearch_url
ELASTICSEARCH_API_KEY=your_api_key

# FatSecret API
FATSECRET_CLIENT_ID=your_client_id
FATSECRET_CLIENT_SECRET=your_client_secret

# OpenAI
OPENAI_API_KEY=your_openai_key

# NUEVO: Control de crawler
FATSECRET_MAX_PAGES_PER_QUERY=10  # Ajustable según límite de API
FATSECRET_MAX_DAILY_CALLS=4500    # Límite seguro (de 5000)
```

---

## 📊 RESULTADOS ESPERADOS

### Antes (actual):
```
Ejercicios: 873 (Yuhonas)
Recetas: ~3,500 (MealDB: 666 + FatSecret: ~2,800)
  - Con macros completos: ~2,800 (solo FatSecret)
  - Sin macros: ~666 (MealDB)
```

### Después (optimizado):
```
Ejercicios: 873 (Yuhonas - sin cambios, API no tiene más)
Recetas: 15,000-19,000 (MealDB: 666 + FatSecret: 14,000-18,000)
  - Con macros completos: 14,000-18,000 (FatSecret)
  - Sin macros: ~666 (MealDB)
  - Cobertura: 80-100% de las 19,000 recetas de FatSecret
```

### Opcional (Fase 2):
```
Alimentos individuales: 50,000-100,000+ (nuevo índice)
  - Categorizado por tipo (generic, brand, restaurant)
  - Información nutricional completa por serving
```

---

## 🚨 CONSIDERACIONES IMPORTANTES

### 1. Límite de API Calls
- **Plan gratuito:** 5,000 calls/día
- **Estimación de crawler mejorado:**
  - ~100 términos de búsqueda
  - ~10 páginas promedio por término = 1,000 búsquedas
  - ~15,000 detalles de recetas = 15,000 calls
  - **Total: ~16,000 calls** ⚠️ EXCEDE EL LÍMITE

**SOLUCIÓN:**
```python
# Estrategia de ejecución en múltiples días
def fetch_fatsecret_recipes_BATCHED():
    """
    Dividir extracción en 4 días:
    - Día 1: Términos 1-25 (4,000 calls)
    - Día 2: Términos 26-50 (4,000 calls)
    - Día 3: Términos 51-75 (4,000 calls)
    - Día 4: Términos 76-100 (4,000 calls)
    """
    # Ver implementación en código final
```

### 2. Rate Limiting
- Agregar `time.sleep()` entre calls
- Actual: 0.1s entre recetas ✅
- Actual: 0.3s entre páginas ✅
- Actual: 0.5s entre términos ✅
- **Mantener valores actuales**

### 3. Datos multiidioma
- Usuario debe ver en **inglés** siempre
- FatSecret devuelve data en inglés por defecto ✅
- No se necesitan cambios

### 4. Deduplicación
- `seen_ids` ya implementado ✅
- Funciona correctamente

---

## 📝 RESUMEN DE ACCIONES

### ✅ HACER:
1. Agregar función `get_all_recipe_types()` ⭐
2. Expandir lista de queries (48 → 100+ términos) ⭐
3. Aumentar `max_pages` de 5 a 10 por término ⭐
4. Agregar tracking de cobertura en logs ⭐
5. Implementar estrategia de batching (multi-día) ⭐

### ❌ NO HACER:
1. ❌ Buscar ejercicios de gimnasio en FatSecret (no existen)
2. ❌ Cambiar fuente de ejercicios (mantener Yuhonas)
3. ❌ Exceder 5,000 API calls/día (riesgo de ban)
4. ❌ Traducir recetas (ya vienen en inglés)

### 🤔 CONSIDERAR (Futuro):
1. Agregar índice de alimentos individuales (foods)
2. Upgrade a plan Premier (unlimited calls, 58 países)
3. Implementar image recognition (requiere Premier)
4. Agregar NLP para parsing de recetas (requiere Premier)

---

## 📖 REFERENCIAS

### Documentación oficial:
- Platform API: https://platform.fatsecret.com/platform-api
- Guides: https://platform.fatsecret.com/docs/guides
- Recipe Types: https://platform.fatsecret.com/docs/v2/recipe_types.get
- Exercises: https://platform.fatsecret.com/docs/v2/exercises.get
- Foods Search: https://platform.fatsecret.com/docs/v2/foods.autocomplete

### Fuentes alternativas mantenidas:
- Ejercicios: https://github.com/yuhonas/free-exercise-db
- Recetas (backup): https://www.themealdb.com/api.php

---

## 🎉 CONCLUSIÓN

**FatSecret API tiene capacidad para 19,000+ recetas**, pero el crawler actual solo extrae ~15% de ellas.

**Con las optimizaciones propuestas, se puede alcanzar 80-100% de cobertura** (15,000-19,000 recetas) dividiendo la extracción en **4 días** para respetar el límite de API calls.

**Los ejercicios de FatSecret son limitados** (solo tipos básicos para cardio), por lo que **Yuhonas sigue siendo la mejor fuente** para ejercicios de gimnasio detallados.

El usuario verá **todo en inglés** como requiere, ya que FatSecret devuelve data en inglés por defecto.

---

*Documento generado por investigación exhaustiva del FatSecret Platform API.*
*Última actualización: 2026-06-06*
