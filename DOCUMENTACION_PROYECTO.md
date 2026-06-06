# 🏋️ RAG Health & Fitness POC - Documentación Completa del Proyecto

## 📋 Tabla de Contenidos
1. [Visión General del Proyecto](#visión-general-del-proyecto)
2. [Arquitectura del Sistema](#arquitectura-del-sistema)
3. [Requerimientos Técnicos](#requerimientos-técnicos)
4. [Componentes Principales](#componentes-principales)
5. [Flujo de Datos](#flujo-de-datos)
6. [Guía de Uso](#guía-de-uso)
7. [Integración con Tsinghua Workshop](#integración-con-tsinghua-workshop)

---

## 🎯 Visión General del Proyecto

### Propósito
Este proyecto implementa un sistema **RAG (Retrieval-Augmented Generation)** especializado en fitness y nutrición que combina:
- 🔍 **Búsqueda semántica vectorial** con Elasticsearch
- 🤖 **Generación de respuestas inteligentes** con OpenAI GPT
- 📊 **Planificación nutricional personalizada** basada en perfil de usuario
- 💪 **Recomendaciones de ejercicios** adaptadas a objetivos

### Contexto Académico: Tsinghua Workshop
Este proyecto se desarrolla en el contexto del **Tsinghua Workshop** sobre LLM y Search, combinando técnicas modernas de:
- Information Retrieval (IR)
- Large Language Models (LLMs)
- Vector Search
- Retrieval-Augmented Generation (RAG)

El sistema demuestra cómo los LLMs pueden mejorar significativamente los sistemas de búsqueda tradicionales mediante:
1. **Comprensión semántica** de consultas en lenguaje natural
2. **Generación contextual** de respuestas personalizadas
3. **Integración de múltiples fuentes** de datos heterogéneos

---

## 🏗️ Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                      CAPA DE USUARIO                        │
│  (FastAPI REST API + Frontend - Puerto 8000)               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  CAPA DE EMBEDDINGS                         │
│  (SentenceTransformer: all-MiniLM-L6-v2)                   │
│  Convierte texto → vectores de 384 dimensiones             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│               CAPA DE BÚSQUEDA VECTORIAL                    │
│  (Elasticsearch Cloud con kNN Search)                       │
│  Índices: exercises, recipes                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│             CAPA DE GENERACIÓN (LLM)                        │
│  (OpenAI GPT-4o-mini)                                       │
│  Genera planes personalizados basados en contexto          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  FUENTES DE DATOS                           │
│  • GitHub Yuhonas (Ejercicios)                              │
│  • TheMealDB (Recetas básicas)                              │
│  • FatSecret API (Recetas con macros detallados)            │
└─────────────────────────────────────────────────────────────┘
```

### Componentes Clave

#### 1. **main.py** - API FastAPI (Servicio Principal)
- 🌐 Servidor REST API con FastAPI
- 🔐 CORS habilitado para acceso cross-origin
- 📊 Endpoints:
  - `/health` - Health check del sistema
  - `/api/recommend` - Generación de planes personalizados

#### 2. **crawler.py** - Sistema de Extracción e Indexación
- 🕷️ Web crawler multi-fuente
- 🔄 Estrategia: **TRUNCATE & LOAD** (reinicio completo de BD)
- 🧮 Generación automática de embeddings vectoriales

#### 3. **query.py** - Script de Consulta CLI
- 💬 Interface de línea de comandos para testing
- 🔍 Búsqueda semántica directa
- 🤖 Generación de respuestas con fallback

---

## 📦 Requerimientos Técnicos

### Dependencias de Python
```python
# Core Framework
fastapi                 # Framework web moderno
uvicorn                 # Servidor ASGI

# Machine Learning & AI
sentence-transformers   # Modelo de embeddings (all-MiniLM-L6-v2)
openai                  # SDK de OpenAI para GPT

# Database & Search
elasticsearch          # Cliente de Elasticsearch
python-dotenv          # Gestión de variables de entorno

# Data Processing
requests               # HTTP requests para APIs externas
pydantic              # Validación de datos

# Utilidades
json                   # Procesamiento JSON nativo
string                 # Manipulación de strings
time                   # Control de delays
```

### Variables de Entorno (.env)
```bash
# OpenMP (fix para librerías duplicadas)
KMP_DUPLICATE_LIB_OK=TRUE

# Elasticsearch Cloud
ELASTICSEARCH_URL=https://[tu-instancia].gcp.cloud.es.io:443
ELASTICSEARCH_API_KEY=[tu-api-key]

# OpenAI
OPENAI_API_KEY=sk-proj-[tu-api-key]

# APIs de Datos Nutricionales
FATSECRET_CLIENT_ID=[tu-client-id]
FATSECRET_CLIENT_SECRET=[tu-client-secret]
```

### Infraestructura Externa
- **Elasticsearch Cloud** (GCP US-Central1)
  - Índices con búsqueda kNN
  - Vectores de 384 dimensiones
  - Similitud coseno

- **OpenAI API**
  - Modelo: gpt-4o-mini
  - Temperatura: 0.2 (determinista)
  - Max tokens: 4000

---

## 🔧 Componentes Principales

### 📄 main.py - Servidor API FastAPI

#### **Funcionalidades Core**

##### 1. Cálculos Metabólicos
```python
def calculate_bmr(weight_kg, height_cm, age, sex)
```
- **Propósito**: Calcula Tasa Metabólica Basal (BMR) usando ecuación de Mifflin-St Jeor
- **Fórmulas**:
  - Hombre: `BMR = 10×peso + 6.25×altura - 5×edad + 5`
  - Mujer: `BMR = 10×peso + 6.25×altura - 5×edad - 161`

```python
def calculate_tdee(bmr, activity_factor)
```
- **Propósito**: Calcula Gasto Energético Diario Total (TDEE)
- **Factores de Actividad**:
  - Sedentario: 1.2
  - Ligeramente activo: 1.375
  - Moderadamente activo: 1.55
  - Muy activo: 1.725
  - Extra activo: 1.9

##### 2. Clasificación de Objetivos
```python
def classify_goal(query)
```
- **Entrada**: Consulta del usuario en lenguaje natural
- **Salida**: `(goal_type, calorie_adjustment, protein_multiplier)`
- **Tipos de Objetivos**:
  - `weight_loss`: -20% calorías, 2.0g proteína/kg
  - `muscle_gain`: +15% calorías, 1.8g proteína/kg
  - `recomp`: -10% calorías, 2.2g proteína/kg
  - `maintenance`: 0% calorías, 1.6g proteína/kg

##### 3. Validación de Seguridad
```python
def detect_unsafe_goal(query, target_calories, sex, tdee)
```
- **Protecciones**:
  - Mínimo calórico: 1500 kcal (hombre), 1200 kcal (mujer)
  - Déficit máximo: 25% del TDEE
  - Superávit máximo: 20% del TDEE
  - Detección de metas extremas/peligrosas

##### 4. Búsqueda Vectorial en Elasticsearch
```python
def search_elasticsearch(index_name, query_vector, k=3, filter_zero_macros=False)
```
- **Parámetros**:
  - `index_name`: "exercises" o "recipes"
  - `query_vector`: Vector de 384 dimensiones
  - `k`: Número de resultados
  - `filter_zero_macros`: Filtrar recetas sin información nutricional

- **Características**:
  - Búsqueda kNN (k-Nearest Neighbors)
  - `num_candidates`: 150 (sobresampling para mejor recall)
  - Priorización de recetas de FatSecret (prefijo `rec_fs_`)
  - Filtrado de macros en cero (evita alucinaciones)

##### 5. Validación de Plan Nutricional
```python
def validate_nutrition_plan(daily_totals, target_calories, target_protein_g, all_meal_options, all_snack_options)
```
- **Validaciones**:
  - Calorías dentro del 5% de tolerancia
  - Proteína mínima del 90% del target
  - Recálculo de macros por día
  - Detección de índices de recetas inválidos

##### 6. Endpoint Principal: `/api/recommend`
```python
@app.post("/api/recommend", response_model=RecommendationResponse)
def get_recommendation(request: QueryRequest)
```

**Pipeline de Procesamiento**:

1. **Generación de Embeddings**
   ```python
   query_vector = model.encode(request.query).tolist()
   ```

2. **Búsqueda Multi-índice**
   - 12 ejercicios más relevantes
   - 30 recetas principales
   - 15 snacks (búsqueda específica según objetivo)

3. **Cálculos Personalizados**
   - BMR → TDEE → Calorías objetivo
   - Proteínas (según peso y objetivo)
   - Grasas (27.5% de calorías)
   - Carbohidratos (calorías restantes)

4. **Formateo de Opciones**
   ```python
   def format_recipe_with_portions(recipe)
   ```
   - 4 porciones por receta: 0.5×, 1×, 1.5×, 2×
   - Macros pre-calculados para cada porción

5. **Generación con LLM**
   - Prompt estructurado en inglés
   - Límites estrictos de índices
   - Schema JSON obligatorio
   - Temperatura 0.2 (baja variabilidad)

6. **Post-procesamiento**
   - Validación de macros
   - Inyección de `daily_totals` (corrige BUG #2)
   - Generación de `macro_bars` sin targets
   - Warnings de seguridad

**Modelo de Datos de Respuesta**:
```python
{
  "plan_summary": {
    "title": str,
    "goal_detected": str,
    "short_summary": str,
    "focus": str,
    "difficulty_level": str
  },
  "user_profile_summary": {...},
  "nutrition_summary": {
    "avg_daily_calories": int,
    "avg_daily_protein_g": float,
    "avg_daily_carbs_g": float,
    "avg_daily_fats_g": float
  },
  "macro_bars": [...],
  "meal_options": [...],
  "snack_options": [...],
  "workout_options": [...],
  "weekly_calendar": [
    {
      "day": str,
      "meals": [...],
      "workout": {...},
      "daily_totals": {...},  # ← Inyectado por Python
      "notes": str
    }
  ],
  "ai_recommendations": {...}
}
```

---

### 🕷️ crawler.py - Sistema de Indexación

#### **Estrategia: TRUNCATE & LOAD**
- Borra índices existentes completamente
- Crea índices desde cero con mappings actualizados
- Garantiza consistencia total de datos

#### **Fuentes de Datos**

##### 1. **GitHub Yuhonas Exercise Database**
```python
def fetch_github_yuhonas_dump()
```
- **URL**: `https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/dist/exercises.json`
- **Datos Extraídos**:
  - Nombre del ejercicio
  - Músculos primarios y secundarios
  - Equipo necesario
  - Instrucciones detalladas
  - Estimación MET (Metabolic Equivalent of Task)

##### 2. **TheMealDB API**
```python
def fetch_mealdb_recipes()
```
- **Método**: Búsqueda alfabética A-Z
- **Datos Extraídos**:
  - Nombre de receta
  - Categoría (Vegetarian, Beef, Chicken, etc.)
  - Ingredientes con medidas
  - Instrucciones de preparación
- **Limitación**: Sin información nutricional (macros en 0)

##### 3. **FatSecret API** (Extracción Profunda)
```python
def fetch_fatsecret_recipes()
```
- **Autenticación**: OAuth 2.0 Client Credentials
- **Categorías**: `['chicken', 'beef', 'pork', 'salad', 'vegetarian', 'vegan', 'pasta', 'fish', 'soup', 'keto']`
- **Datos Extraídos**:
  - Información nutricional completa (16+ campos de macros)
  - Rating de usuarios
  - Tiempos de preparación y cocción
  - Categorías/tags reales de la API
  - URLs e imágenes de recetas
  - Ingredientes con descripciones detalladas
  - Instrucciones paso a paso

**Macros Extraídos de FatSecret**:
```python
'macros': {
    'calories', 'protein_g', 'carbs_g', 'fats_g',
    'saturated_fat_g', 'polyunsaturated_fat_g', 'monounsaturated_fat_g',
    'cholesterol_mg', 'sodium_mg', 'potassium_mg',
    'fiber_g', 'sugar_g',
    'vitamin_a_dv', 'vitamin_c_dv', 'calcium_dv', 'iron_dv'
}
```

#### **Mappings de Elasticsearch**

##### **Índice: exercises**
```python
{
    "name": {"type": "text"},
    "target_muscle": {"type": "keyword"},
    "secondary_muscles": {"type": "keyword"},
    "equipment": {"type": "keyword"},
    "estimated_met": {"type": "float"},
    "search_context": {"type": "text"},
    "embedding": {
        "type": "dense_vector",
        "dims": 384,
        "index": True,
        "similarity": "cosine"
    }
}
```

##### **Índice: recipes**
```python
{
    "name": {"type": "text"},
    "recipe_description": {"type": "text"},
    "recipe_url": {"type": "keyword"},
    "recipe_image": {"type": "keyword"},
    "rating": {"type": "float"},
    "ready_in_minutes": {"type": "integer"},
    "diets": {"type": "keyword"},
    "macros": {
        "properties": {
            "calories": {"type": "integer"},
            "protein_g": {"type": "float"},
            # ... +14 campos nutricionales
        }
    },
    "embedding": {
        "type": "dense_vector",
        "dims": 384,
        "index": True,
        "similarity": "cosine"
    }
}
```

#### **Proceso de Indexación**

1. **Generación de Embeddings**
   ```python
   def generate_embedding(text)
   ```
   - Modelo: `sentence-transformers/all-MiniLM-L6-v2`
   - Entrada: Campo `search_context` (JSON completo del documento)
   - Salida: Vector de 384 dimensiones

2. **Bulk Indexing**
   ```python
   def bulk_index(es_client, index_name, documents)
   ```
   - Uso de `helpers.bulk()` para eficiencia
   - Procesamiento batch de vectores

3. **Deduplicación**
   - Uso de diccionario por `id` para fusionar recetas de múltiples fuentes
   - Prioridad: FatSecret > TheMealDB (por calidad de datos)

---

### 🔍 query.py - Script de Consulta CLI

#### **Propósito**
Script standalone para testing de búsqueda y generación sin necesidad de levantar el servidor completo.

#### **Flujo de Ejecución**

1. **Validación de Entorno**
   ```python
   # Verifica ELASTICSEARCH_URL, ELASTICSEARCH_API_KEY
   # OPENAI_API_KEY es opcional (usa fallback)
   ```

2. **Carga de Modelo de Embeddings**
   ```python
   model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
   ```

3. **Búsqueda en Elasticsearch**
   ```python
   def search_elasticsearch(es_client, query_embedding)
   ```
   - Top 3 ejercicios
   - Top 3 recetas
   - Parse de `search_context` JSON

4. **Generación de Respuesta**
   ```python
   def call_openai(user_query, exercises, recipes)
   ```
   - Modelos: `gpt-4o-mini` → `gpt-3.5-turbo` (fallback)
   - Temperatura: 0.7
   - Max tokens: 800

5. **Fallback Sin OpenAI**
   ```python
   def generate_fallback_response(exercises, recipes)
   ```
   - Respuesta estructurada sin LLM
   - Recomendaciones genéricas
   - Tips de entrenamiento y nutrición

#### **Uso**
```bash
python query.py "I want to build muscle and lose fat"
python query.py "Necesito recetas vegetarianas altas en proteína"
```

---

## 🔄 Flujo de Datos Completo

### 1️⃣ Fase de Indexación (Una vez)
```
[APIs Externas] 
    ↓ (HTTP requests)
[crawler.py] 
    ↓ (raw data)
[SentenceTransformer] 
    ↓ (embeddings 384D)
[Elasticsearch Cloud] 
    ↓ (indexes creados)
✅ Base de Datos Vectorial Lista
```

### 2️⃣ Fase de Consulta (Cada request)
```
[Usuario] → "Quiero ganar músculo"
    ↓
[main.py/FastAPI] → Recibe QueryRequest
    ↓
[SentenceTransformer] → Genera vector de consulta
    ↓
[Elasticsearch kNN] → Búsqueda por similitud coseno
    ↓ (top-k results)
[main.py] → Calcula BMR, TDEE, macros
    ↓
[OpenAI GPT] → Genera plan personalizado con JSON schema
    ↓
[main.py] → Valida, recalcula, inyecta daily_totals
    ↓
[Usuario] ← Recibe plan completo de 7 días
```

---

## 🚀 Guía de Uso

### Instalación

```bash
# 1. Clonar repositorio
git clone <repo-url>
cd tsinghua_workshop

# 2. Instalar dependencias
pip install fastapi uvicorn elasticsearch sentence-transformers openai python-dotenv requests pydantic

# 3. Configurar .env (ver sección de Requerimientos)
cp .env.example .env
# Editar .env con tus credenciales

# 4. Indexar datos (primera vez o para actualizar)
python crawler.py

# 5. Iniciar servidor
uvicorn main:app --reload --port 8000
```

### Testing

#### Opción 1: Script CLI
```bash
python query.py "I want to lose weight and build muscle"
```

#### Opción 2: API REST
```bash
curl -X POST http://localhost:8000/api/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "query": "I want to lose weight and build muscle",
    "user_profile": {
      "age": 25,
      "sex": "male",
      "weight_kg": 80,
      "height_cm": 175,
      "activity_level": "moderately_active"
    }
  }'
```

#### Opción 3: Health Check
```bash
curl http://localhost:8000/health
```

---

## 🎓 Integración con Tsinghua Workshop

### Conceptos de IR y LLM Aplicados

#### 1. **Vector Search (Information Retrieval)**
- **Embeddings Semánticos**: Convierte texto en representaciones densas que capturan significado
- **Similitud Coseno**: Métrica de distancia para encontrar documentos relevantes
- **kNN Search**: Algoritmo eficiente para búsqueda en espacios de alta dimensionalidad

#### 2. **Retrieval-Augmented Generation (RAG)**
- **Retrieval**: Búsqueda vectorial en Elasticsearch (top-k más relevantes)
- **Augmentation**: Enriquecimiento del prompt del LLM con contexto recuperado
- **Generation**: GPT genera respuesta basada en documentos reales (no alucina)

#### 3. **Mejoras sobre Search Tradicional**
- **Búsqueda por significado** vs. keyword matching
- **Respuestas naturales** vs. lista de resultados
- **Personalización** basada en perfil de usuario
- **Validación y corrección** de alucinaciones del LLM

### Alineación con Materiales del Workshop

#### De "WIR-1.intro-IR(26.2.28).pdf"
- ✅ **Boolean Retrieval**: Superado con búsqueda vectorial
- ✅ **Vector Space Model**: Implementado con SentenceTransformers
- ✅ **Relevance Feedback**: Implícito en ajustes de macros

#### De "LLM_and_Search_Report_Tsinghua_Expert_Expanded.pdf"
- ✅ **Hybrid Search**: Combinación de búsqueda vectorial + filtros estructurados
- ✅ **Prompt Engineering**: Schema JSON estricto, temperature 0.2
- ✅ **Hallucination Mitigation**: Validación post-generación, índices limitados

### Casos de Uso Demostrados

1. **Pregunta: "¿Qué comer para ganar músculo?"**
   - IR: Busca recetas altas en proteína
   - LLM: Genera plan de comidas con timing y porciones

2. **Pregunta: "Rutina de ejercicios para principiantes"**
   - IR: Filtra ejercicios por equipo y dificultad
   - LLM: Estructura programa de 7 días con progresión

3. **Pregunta: "Plan vegetariano para perder peso"**
   - IR: Combina filtros (vegetarian tag + macros bajos)
   - LLM: Balancea déficit calórico con suficiencia nutricional

---

## 🛡️ Manejo de Errores y Edge Cases

### Protecciones Implementadas

1. **Metas Nutricionales Peligrosas**
   - Detección de frases extremas ("lose 20kg in 2 weeks")
   - Ajuste automático a mínimos seguros
   - Warnings visibles en `ai_recommendations.safety_notes`

2. **Validación de Índices**
   - Rango permitido: 0 a len(options)-1
   - Warnings por índices fuera de rango
   - Salto de recetas inválidas sin crash

3. **Macros Faltantes**
   - Filtro `filter_zero_macros=True` para recetas
   - Recetas de TheMealDB (sin macros) usadas solo para variedad
   - Priorización de FatSecret (macros completos)

4. **Alucinaciones del LLM**
   - BUG #1: Límites explícitos en prompt (MAX_MEAL_OPTIONS=15)
   - BUG #2: Python recalcula macros (no confía en LLM)
   - BUG #4: `_source: True` en Elasticsearch (no text strings)

5. **Fallos de APIs Externas**
   - Fallback a modelo GPT alternativo
   - Generación de respuesta estructurada sin OpenAI
   - Logs detallados de errores HTTP

---

## 📊 Métricas y Performance

### Tamaño de Datos
- **Ejercicios**: ~800-1000 documentos (GitHub Yuhonas)
- **Recetas**: ~500-700 documentos
  - TheMealDB: ~400 recetas (A-Z)
  - FatSecret: ~100-300 recetas (según tier API)

### Dimensiones de Embeddings
- **384 dimensiones** (all-MiniLM-L6-v2)
- Balance óptimo: rapidez vs. calidad semántica

### Tiempos de Respuesta Estimados
- Búsqueda vectorial: 50-100ms
- Generación LLM: 2-5 segundos
- Total end-to-end: ~3-7 segundos

---

## 🔮 Futuras Mejoras

### Técnicas
1. **Reranking con Cross-Encoders**: Mejorar recall de top-k
2. **Hybrid Search**: Combinar BM25 + vectorial
3. **Fine-tuning de Embeddings**: Modelo específico de dominio fitness
4. **Caching de Planes**: Redis para consultas repetidas

### Funcionalidades
1. **Tracking de Progreso**: Base de datos de usuarios
2. **Ajuste Adaptativo**: Reajuste semanal de macros
3. **Sustituciones Inteligentes**: Swap de recetas por alergias
4. **Integración con Wearables**: Apple Health, Fitbit, etc.

---

## 📚 Referencias

### Documentos del Workshop
- `WIR-1.intro-IR(26.2.28).pdf` - Fundamentos de Information Retrieval
- `LLM_and_Search_Report_Tsinghua_Expert_Expanded.pdf` - RAG y LLM aplicados
- `LLM_AND_SEARCH.pptx` - Presentación del taller
- `LLM_and_Search_Tsinghua.pptx` - Material de Tsinghua

### APIs Utilizadas
- [Elasticsearch Cloud](https://www.elastic.co/cloud/)
- [OpenAI GPT](https://platform.openai.com/docs/)
- [FatSecret Platform API](https://platform.fatsecret.com/)
- [TheMealDB](https://www.themealdb.com/api.php)
- [Yuhonas Exercise DB](https://github.com/yuhonas/free-exercise-db)

### Modelos de ML
- [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
- [OpenAI GPT-4o-mini](https://platform.openai.com/docs/models/gpt-4o-mini)

---

## 👥 Autor
Proyecto desarrollado para el **Tsinghua Workshop on LLM and Search**

## 📄 Licencia
Este proyecto es de código abierto y está disponible bajo la licencia MIT.

---

**Última actualización**: Junio 2026
