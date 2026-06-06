# 📋 Requerimientos del Sistema - RAG Health & Fitness POC

## 🎯 Objetivo del Sistema

Desarrollar un sistema de Retrieval-Augmented Generation (RAG) que genere planes personalizados de fitness y nutrición basándose en:
- Perfil biométrico del usuario (edad, peso, altura, sexo, nivel de actividad)
- Objetivos expresados en lenguaje natural
- Base de conocimiento de ejercicios y recetas verificadas
- Cálculos metabólicos científicos (BMR, TDEE)

---

## 📚 Requerimientos Funcionales

### RF-001: Búsqueda Semántica de Ejercicios
**Prioridad**: Alta
**Descripción**: El sistema debe buscar ejercicios relevantes usando búsqueda vectorial semántica.

**Criterios de Aceptación**:
- ✅ Convertir consulta de usuario a vector de 384 dimensiones
- ✅ Buscar top-12 ejercicios más similares usando kNN
- ✅ Retornar ejercicios con: nombre, músculo objetivo, equipo, MET, instrucciones

**Ejemplo**:
```
Entrada: "ejercicios para pecho con mancuernas"
Salida: [Dumbbell Bench Press, Dumbbell Flyes, Incline Dumbbell Press, ...]
```

---

### RF-002: Búsqueda Semántica de Recetas
**Prioridad**: Alta
**Descripción**: El sistema debe buscar recetas con información nutricional completa.

**Criterios de Aceptación**:
- ✅ Búsqueda principal: top-30 recetas relevantes
- ✅ Búsqueda secundaria: top-15 snacks (consulta enriquecida por objetivo)
- ✅ Filtrar recetas con macros en cero (TheMealDB)
- ✅ Priorizar recetas de FatSecret (macros completos)
- ✅ Deduplicar por recipe_id

---

### RF-003: Cálculo de Metabolismo Basal (BMR)
**Prioridad**: Alta
**Descripción**: Calcular la tasa metabólica basal usando la ecuación de Mifflin-St Jeor.

**Criterios de Aceptación**:
- ✅ Soportar múltiples variantes de sexo: "male", "female", "hombre", "mujer", "m", "f"
- ✅ Fórmula hombres: `BMR = 10×peso + 6.25×altura - 5×edad + 5`
- ✅ Fórmula mujeres: `BMR = 10×peso + 6.25×altura - 5×edad - 161`
- ✅ Retornar valor redondeado a 2 decimales

**Ejemplo**:
```
Entrada: weight_kg=80, height_cm=175, age=25, sex="male"
Salida: 1825.00 kcal/día
```

---

### RF-004: Cálculo de TDEE (Total Daily Energy Expenditure)
**Prioridad**: Alta
**Descripción**: Calcular el gasto energético diario total multiplicando BMR por factor de actividad.

**Factores de Actividad**:
| Nivel | Factor | Descripción |
|-------|--------|-------------|
| sedentary | 1.2 | Poco o ningún ejercicio |
| lightly_active | 1.375 | Ejercicio ligero 1-3 días/semana |
| moderately_active | 1.55 | Ejercicio moderado 3-5 días/semana |
| very_active | 1.725 | Ejercicio intenso 6-7 días/semana |
| extra_active | 1.9 | Ejercicio muy intenso + trabajo físico |

**Criterios de Aceptación**:
- ✅ Aplicar factor de actividad correcto
- ✅ Default a "moderately_active" (1.55) si no se especifica
- ✅ Retornar valor entero

---

### RF-005: Clasificación Automática de Objetivos
**Prioridad**: Alta
**Descripción**: Analizar consulta del usuario y determinar objetivo fitness automáticamente.

**Palabras Clave**:

```python
weight_loss_keywords = ['perder', 'bajar', 'lose', 'weight loss', 'adelgazar', 
                        'reducir', 'grasa', 'fat', 'cut', 'deficit']
muscle_gain_keywords = ['ganar', 'aumentar', 'bulk', 'masa', 'gain', 'muscle', 
                        'músculo', 'muscular', 'hypertrophy']
maintenance_keywords = ['mantener', 'maintain', 'tonificar', 'tone']
```

**Reglas de Clasificación**:
| Condición | Objetivo | Ajuste Calórico | Proteína (g/kg) |
|-----------|----------|-----------------|-----------------|
| weight_loss + muscle_gain | recomp | -10% | 2.2 |
| Solo weight_loss | weight_loss | -20% | 2.0 |
| Solo muscle_gain | muscle_gain | +15% | 1.8 |
| maintenance o ninguno | maintenance | 0% | 1.6 |

**Criterios de Aceptación**:
- ✅ Detectar objetivos en español e inglés
- ✅ Priorizar "recomp" si detecta ambos objetivos
- ✅ Retornar tupla: `(goal_type, calorie_adjustment, protein_multiplier)`

---

### RF-006: Validación de Seguridad Nutricional
**Prioridad**: Crítica
**Descripción**: Detectar y corregir metas nutricionales peligrosas o irrealistas.

**Validaciones**:

1. **Mínimos Calóricos Seguros**
   - Hombre: 1500 kcal/día
   - Mujer: 1200 kcal/día

2. **Déficit Máximo**: 25% del TDEE

3. **Superávit Máximo**: 20% del TDEE

4. **Frases Extremas Detectadas**:
   ```python
   extreme_phrases = ['lose 10', 'lose 20', 'perder 10', 'perder 20',
                      'in 2 weeks', 'en 2 semanas', 'in 1 week', 'en 1 semana',
                      'crash', 'extreme', 'fast', 'rapid', 'rapido', 'extremo',
                      'starvation', 'starve', 'purge', 'hambre']
   ```

**Criterios de Aceptación**:
- ✅ Ajustar automáticamente calorías peligrosas
- ✅ Generar warnings específicos
- ✅ Incluir warnings en `ai_recommendations.safety_notes`
- ✅ Retornar: `(is_unsafe, adjusted_calories, warnings)`

**Ejemplo**:
```
Entrada: target_calories=800, sex="female", tdee=2000
Salida: (True, 1200, ["Target calories (800 kcal) adjusted to safe minimum (1200 kcal)"])
```

---

### RF-007: Cálculo Automático de Macronutrientes
**Prioridad**: Alta
**Descripción**: Calcular distribución óptima de macronutrientes según objetivo.

**Fórmulas**:
```python
# Proteína
target_protein_g = peso_kg × protein_multiplier

# Grasas (27.5% de calorías totales)
target_fats_g = (target_calories × 0.275) / 9

# Carbohidratos (calorías restantes)
protein_calories = target_protein_g × 4
fat_calories = target_fats_g × 9
target_carbs_g = (target_calories - protein_calories - fat_calories) / 4
```

**Criterios de Aceptación**:
- ✅ Proteína basada en peso corporal
- ✅ Grasas en 27.5% fijo
- ✅ Carbohidratos llenan el resto
- ✅ Valores redondeados (proteína y carbos a enteros, grasas a enteros)

---

### RF-008: Generación de Plan con LLM
**Prioridad**: Alta
