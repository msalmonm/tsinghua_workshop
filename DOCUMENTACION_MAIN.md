# 📘 Documentación Técnica: main.py

## 🎯 Propósito
`main.py` es el servidor API principal del sistema RAG Health & Fitness. Implementa un servicio REST con FastAPI que:
- Recibe consultas de usuarios con su perfil nutricional
- Realiza búsqueda vectorial semántica en Elasticsearch
- Genera planes personalizados de 7 días usando OpenAI GPT
- Valida y corrige la información nutricional

---

## 🏗️ Arquitectura del Módulo

### Inicialización Global
```python
# Configuración de entorno
load_dotenv()
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

# Clientes globales (singleton pattern)
es_client = Elasticsearch(...)
openai_client = OpenAI(...)
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
```

### FastAPI Application
```python
app = FastAPI(title="Fitness RAG API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
```

---

## 📊 Modelos de Datos (Pydantic)

### UserProfile
```python
class UserProfile(BaseModel):
    age: int
    sex: str  # "male", "female", "hombre", "mujer", etc.
    weight_kg: float
    height_cm: float
    activity_level: str = "moderately_active"
```

### QueryRequest
```python
class QueryRequest(BaseModel):
    query: str  # Objetivo del usuario en lenguaje natural
    user_profile: UserProfile
```

### RecommendationResponse
```python
class RecommendationResponse(BaseModel):
    response: str  # JSON string del plan completo
    plan: dict  # Plan estructurado
    raw_data: dict  # Datos brutos de Elasticsearch
```

---

## 🔧 Funciones Core

### 1. calculate_bmr(weight_kg, height_cm, age, sex)
**Propósito**: Calcula la Tasa Metabólica Basal (BMR) usando la ecuación de Mifflin-St Jeor.

**Parámetros**:
- `weight_kg` (float): Peso en kilogramos
- `height_cm` (float): Altura en centímetros
- `age` (int): Edad en años
- `sex` (str): Sexo biológico

**Retorno**: `float` - BMR en kcal/día

**Fórmulas**:
```python
# Hombre
BMR = 10 × peso + 6.25 × altura - 5 × edad + 5

# Mujer
BMR = 10 × peso + 6.25 × altura - 5 × edad - 161
```

**Ejemplo**:
```python
bmr = calculate_bmr(80, 175, 25, "male")  # → ~1825 kcal/día
```

---

### 2. get_activity_factor(activity_level)
**Propósito**: Convierte nivel de actividad en multiplicador TDEE.

**Factores de Actividad**:
| Nivel | Multiplicador | Descripción |
|-------|---------------|-------------|
| sedentary | 1.2 | Poco o ningún ejercicio |
| lightly_active | 1.375 | Ejercicio ligero 1-3 días/semana |
| moderately_active | 1.55 | Ejercicio moderado 3-5 días/semana |
| very_active | 1.725 | Ejercicio intenso 6-7 días/semana |
| extra_active | 1.9 | Ejercicio muy intenso + trabajo físico |

---

### 3. calculate_tdee(bmr, activity_factor)
**Propósito**: Calcula el Gasto Energético Diario Total.

**Fórmula**: `TDEE = BMR × Activity Factor`

**Ejemplo**:
```python
tdee = calculate_tdee(1825, 1.55)  # → 2829 kcal/día
```

---

### 4. classify_goal(query)
**Propósito**: Analiza la consulta del usuario y determina su objetivo fitness.

**Parámetros**:
- `query` (str): Consulta en lenguaje natural

**Retorno**: `tuple(goal_type, calorie_adjustment, protein_multiplier)`

**Lógica de Clasificación**:
```python
# Palabras clave de pérdida de peso
weight_loss_keywords = ['perder', 'bajar', 'lose', 'weight loss', 
                        'adelgazar', 'reducir', 'grasa', 'fat', 'cut']

# Palabras clave de ganancia muscular
muscle_gain_keywords = ['ganar', 'aumentar', 'bulk', 'masa', 'gain',
                        'muscle', 'músculo', 'muscular', 'hypertrophy']
```

**Tipos de Objetivos**:
| Objetivo | Ajuste Calórico | Proteína (g/kg) | Descripción |
|----------|-----------------|-----------------|-------------|
| weight_loss | -20% | 2.0 | Déficit para perder grasa |
| muscle_gain | +15% | 1.8 | Superávit para hipertrofia |
| recomp | -10% | 2.2 | Recomposición corporal |
| maintenance | 0% | 1.6 | Mantener peso actual |

**Ejemplo**:
```python
goal_type, cal_adj, protein = classify_goal("Quiero perder grasa y ganar músculo")
# → ('recomp', -0.10, 2.2)
```

---

### 5. apply_goal_adjustment(tdee, calorie_adjustment)
**Propósito**: Aplica el ajuste calórico al TDEE.

**Fórmula**: `Target Calories = TDEE × (1 + adjustment)`

**Ejemplo**:
```python
target = apply_goal_adjustment(2829, -0.20)  # → 2263 kcal
```

---

### 6. detect_unsafe_goal(query, target_calories, sex, tdee)
**Propósito**: Detecta y corrige metas nutricionales peligrosas.

**Validaciones**:

1. **Mínimos Calóricos Seguros**
   ```python
   min_calories = 1500 if sex in ['male', 'hombre', 'm'] else 1200
