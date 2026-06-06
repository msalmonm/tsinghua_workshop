# 🏋️ RAG Health & Fitness POC

Sistema RAG (Retrieval-Augmented Generation) para generación de planes personalizados de fitness y nutrición usando búsqueda vectorial semántica y OpenAI GPT.

## 🎓 Tsinghua Workshop - LLM and Search

Este proyecto demuestra conceptos avanzados de Information Retrieval y Large Language Models:
- Vector Search con Elasticsearch
- Semantic Embeddings con SentenceTransformers
- Retrieval-Augmented Generation (RAG)
- Mitigación de alucinaciones en LLMs

---

## ✨ Características

✅ **Búsqueda Semántica Vectorial** - Encuentra ejercicios y recetas por significado, no solo keywords
✅ **Planes Personalizados de 7 Días** - Basados en edad, peso, altura, sexo y nivel de actividad
✅ **Cálculos Metabólicos Automáticos** - BMR, TDEE, macros optimizados
✅ **Validación de Seguridad** - Detecta y corrige metas nutricionales peligrosas
✅ **Multi-fuente de Datos** - GitHub, TheMealDB, FatSecret API
✅ **Sin Alucinaciones** - Validación post-generación con recálculo de macros

---

## 🚀 Quick Start

### 1. Instalación
```bash
# Clonar repositorio
git clone <repo-url>
cd tsinghua_workshop

# Instalar dependencias
pip install fastapi uvicorn elasticsearch sentence-transformers openai python-dotenv requests pydantic
```

### 2. Configuración
Crear archivo `.env`:
```bash
ELASTICSEARCH_URL=https://[tu-instancia].gcp.cloud.es.io:443
ELASTICSEARCH_API_KEY=[tu-api-key]
OPENAI_API_KEY=sk-proj-[tu-api-key]
FATSECRET_CLIENT_ID=[tu-client-id]
FATSECRET_CLIENT_SECRET=[tu-client-secret]
```

### 3. Indexar Datos
```bash
python crawler.py
# ⏱️ ~5-10 minutos (descarga y procesa ~1000+ documentos)
```

### 4. Iniciar Servidor
```bash
uvicorn main:app --reload --port 8000
```

### 5. Probar API
```bash
# Health check
curl http://localhost:8000/health

# Consulta de ejemplo
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

---

## 📁 Estructura del Proyecto

```
tsinghua_workshop/
├── main.py                    # Servidor FastAPI (API principal)
├── crawler.py                 # Sistema de indexación (TRUNCATE & LOAD)
├── query.py                   # Script CLI para testing
├── .env                       # Variables de entorno (NO SUBIR A GIT)
├── .gitignore                # Archivos ignorados
├── context_dump/             # Materiales del workshop
│   ├── LLM_AND_SEARCH.pptx
│   ├── LLM_and_Search_Report_Tsinghua_Expert_Expanded.pdf
│   ├── LLM_and_Search_Tsinghua.pptx
│   └── WIR-1.intro-IR(26.2.28).pdf
└── DOCUMENTACION_PROYECTO.md # Documentación técnica completa
```

---

## 🔧 Componentes Principales

### 1. **main.py** - API FastAPI

**Endpoints**:
- `GET /health` - Health check del sistema
- `POST /api/recommend` - Genera plan personalizado

**Funcionalidades**:
- Cálculo de BMR/TDEE
- Clasificación automática de objetivos
- Búsqueda vectorial en Elasticsearch
- Generación con OpenAI GPT-4o-mini
- Validación y corrección de macros

### 2. **crawler.py** - Indexación de Datos

**Fuentes de Datos**:
- 🏋️ GitHub Yuhonas (~800 ejercicios)
- 🍽️ TheMealDB (~400 recetas)
- 📊 FatSecret API (~100-300 recetas con macros completos)

**Estrategia**: TRUNCATE & LOAD
- Borra índices existentes
- Crea desde cero con mappings actualizados
- Genera embeddings de 384 dimensiones

### 3. **query.py** - CLI Testing Tool

Permite probar búsquedas sin levantar servidor:
```bash
python query.py "I want to build muscle"
```

---

## 🧠 Arquitectura RAG

```
Usuario → Query
    ↓
[SentenceTransformer] → Vector 384D
    ↓
[Elasticsearch kNN] → Top-K docs
    ↓
[Cálculos Metabólicos] → BMR/TDEE/Macros
    ↓
[OpenAI GPT] + Context → Plan Personalizado
    ↓
[Validación Python] → Corrección de Macros
    ↓
Usuario ← Plan de 7 días (JSON)
```

---

## 📚 Documentación Completa

- **DOCUMENTACION_PROYECTO.md** - Guía técnica completa (arquitectura, funciones, flujos)
- **DOCUMENTACION_MAIN.md** - Detalle de main.py (en progreso)
- **context_dump/** - Materiales del Tsinghua Workshop

---

## 🛡️ Seguridad Nutricional

El sistema incluye validaciones automáticas:
- ✅ Mínimos calóricos seguros (1200 F / 1500 M)
- ✅ Déficit máximo del 25% del TDEE
- ✅ Superávit máximo del 20% del TDEE
- ✅ Detección de frases extremas peligrosas
- ✅ Warnings visibles en respuesta

---

## 📊 Ejemplo de Respuesta

```json
{
  "plan_summary": {
    "title": "7-Day Muscle Building & Fat Loss Plan",
    "goal_detected": "recomposition",
    "difficulty_level": "Intermediate"
  },
  "nutrition_summary": {
    "avg_daily_calories": 2263,
    "avg_daily_protein_g": 176,
    "avg_daily_carbs_g": 234,
    "avg_daily_fats_g": 69
  },
  "weekly_calendar": [
    {
      "day": "Monday",
      "meals": [...],
      "workout": {...},
      "daily_totals": {...},
      "notes": "Focus on compound movements today"
    }
  ],
  "ai_recommendations": {
    "main_tip": "Prioritize protein timing around workouts",
    "safety_notes": []
  }
}
```

---

## 🔍 Tecnologías Utilizadas

| Categoría | Tecnología | Propósito |
|-----------|-----------|-----------|
| Web Framework | FastAPI | API REST moderna y rápida |
| Database | Elasticsearch Cloud | Búsqueda vectorial kNN |
| ML Model | all-MiniLM-L6-v2 | Embeddings semánticos (384D) |
| LLM | OpenAI GPT-4o-mini | Generación de planes |
| Data Sources | FatSecret, TheMealDB, GitHub | Recetas y ejercicios |

---

## 🎓 Conceptos del Workshop Aplicados

### Information Retrieval
- ✅ Vector Space Model
- ✅ Cosine Similarity
- ✅ kNN Search

### Large Language Models
- ✅ Retrieval-Augmented Generation (RAG)
- ✅ Prompt Engineering
- ✅ Hallucination Mitigation
- ✅ Structured Output (JSON schema)

---

## 🚧 Futuras Mejoras

- [ ] Reranking con Cross-Encoders
- [ ] Hybrid Search (BM25 + Vector)
- [ ] Fine-tuning de embeddings
- [ ] Base de datos de usuarios
- [ ] Ajuste adaptativo semanal
- [ ] Integración con wearables

---

## 📄 Licencia

MIT License - Proyecto de código abierto

---

## 🤝 Contribuir

1. Fork el proyecto
2. Crea tu feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push al branch (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

---

## 📧 Contacto

Proyecto desarrollado para el **Tsinghua Workshop on LLM and Search**

---

**⭐ Si este proyecto te fue útil, considera darle una estrella!**
