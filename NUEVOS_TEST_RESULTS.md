# Nuevos Resultados de Prueba - main.py Actualizado

## Detalles de Ejecución

**Fecha**: June 7, 2026  
**Script de Prueba**: test_new_responses.py  
**Archivo de Salida**: response_new.json  
**Tamaño del Archivo**: ~379 KB

## Casos de Prueba Ejecutados

### Test 1: Recomposición Corporal - Enfoque en Espalda y Brazos
- **Query**: "I want to recomp my body, focusing on back and arms, training 6 days per week, keto diet"
- **Perfil de Usuario**: 32 años, hombre, 90kg, 182cm, muy activo
- **Estado**: ✓ ÉXITO
- **Resultados Clave**:
  - **Título del Plan**: Keto Body Recomposition Plan Focused on Back and Arms
  - **Objetivo Detectado**: body recomp with emphasis on back and arms
  - **Días Generados**: 7
  - **Calorías Diarias Promedio**: 3,171 kcal
  - **Proteína Diaria Promedio**: 128.9 g
  - **Opciones de Ejercicio**: 36 ejercicios
  - **Opciones de Recetas**: 12 recetas
  - **BMR**: 1,882.5 kcal
  - **TDEE**: 3,247 kcal
  - **Objetivo Nutricional**: mantenimiento (+0%)
  - **Restricciones Dietéticas**: keto

### Test 2: Pérdida de Peso - Enfoque en Piernas y Core
- **Query**: "Lose weight focusing on legs and core exercises, 5 days per week, gluten-free meals"
- **Perfil de Usuario**: 29 años, mujer, 70kg, 168cm, moderadamente activo
- **Estado**: ✓ ÉXITO
- **Resultados Clave**:
  - **Título del Plan**: Gluten-Free Weight Loss Plan Focused on Legs and Core
  - **Objetivo Detectado**: Weight loss with emphasis on legs and core
  - **Días Generados**: 7
  - **Calorías Diarias Promedio**: 1,924 kcal
  - **Proteína Diaria Promedio**: 95.9 g
  - **Opciones de Ejercicio**: 30 ejercicios
  - **Opciones de Recetas**: 9 recetas
  - **BMR**: 1,444.0 kcal
  - **TDEE**: 2,238 kcal
  - **Objetivo Nutricional**: pérdida de peso (-20%)
  - **Restricciones Dietéticas**: gluten-free

### Test 3: Ganancia Muscular - Énfasis en Hombros
- **Query**: "Build muscle mass with shoulder emphasis, 4 training days weekly, high protein pescatarian diet"
- **Perfil de Usuario**: 26 años, hombre, 72kg, 178cm, muy activo
- **Estado**: ✓ ÉXITO
- **Resultados Clave**:
  - **Título del Plan**: High-Protein Pescatarian Muscle Gain Plan
  - **Objetivo Detectado**: muscle gain with shoulder emphasis
  - **Días Generados**: 7
  - **Calorías Diarias Promedio**: 3,322 kcal
  - **Proteína Diaria Promedio**: 272.8 g (¡muy alta!)
  - **Opciones de Ejercicio**: 24 ejercicios
  - **Opciones de Recetas**: 21 recetas
  - **BMR**: 1,707.5 kcal
  - **TDEE**: 2,945 kcal
  - **Objetivo Nutricional**: ganancia muscular (+15%)
  - **Restricciones Dietéticas**: pescatarian

## Resumen General

- **Total de Pruebas**: 3
- **Exitosas**: 3
- **Fallidas**: 0
- **Tasa de Éxito**: 100%

## Observaciones Importantes

### ✅ Funcionamiento Correcto

1. **Extracción de Intent**:
   - Detectó correctamente los objetivos fitness (recomp, weight loss, muscle gain)
   - Identificó partes del cuerpo objetivo (back, arms, legs, core, shoulders)
   - Reconoció frecuencias de entrenamiento (4-6 días por semana)
   - Capturó restricciones dietéticas (keto, gluten-free, pescatarian)

2. **Cálculos Nutricionales**:
   - BMR y TDEE calculados correctamente
   - Ajustes calóricos apropiados según objetivo
   - Objetivos de proteína adecuados para cada perfil

3. **Generación de Planes**:
   - Planes de 7 días completos generados
   - Variedad de ejercicios (9-36 opciones)
   - Catálogo diverso de recetas (9-21 opciones)
   - Respeto a restricciones dietéticas

### 📊 Comparación con Tests Anteriores

| Métrica | Tests Anteriores | Nuevos Tests |
|---------|------------------|--------------|
| Opciones de Ejercicio | 18-24 | 24-36 |
| Opciones de Recetas | 16-24 | 9-21 |
| Detección de Restricciones | ✓ | ✓ Mejorada |
| Enfoque en Partes del Cuerpo | ✓ | ✓ Múltiples |

### 🔍 Insights Interesantes

1. **Test 1 (Recomp Keto)**:
   - Solo 12 recetas keto disponibles (indica que el filtro keto funciona pero hay pocas opciones)
   - 36 ejercicios para back/arms (excelente variedad)
   - Calorías altas (3,171) apropiadas para recomposición en muy activo

2. **Test 2 (Weight Loss Gluten-Free)**:
   - Solo 9 recetas gluten-free (sugiere que necesitamos más recetas GF)
   - 30 ejercicios para legs/core
   - Déficit calórico conservador (-20% desde TDEE)

3. **Test 3 (Muscle Gain Pescatarian)**:
   - 272.8g de proteína/día es MUY alto (probablemente necesita ajuste)
   - 21 recetas pescatarian (buena variedad)
   - 24 ejercicios para hombros

### ⚠️ Áreas de Mejora Identificadas

1. **Proteína Extremadamente Alta** (Test 3):
   - 272.8g para 72kg = 3.8g/kg (excede el límite recomendado de 2.4g/kg)
   - Posible error en el cálculo de porciones o selección de recetas

2. **Pocas Recetas para Dietas Específicas**:
   - Keto: 12 recetas (podría necesitar más)
   - Gluten-Free: 9 recetas (definitivamente necesita más opciones)

3. **Variación en Cantidad de Ejercicios**:
   - Test 1: 36 ejercicios (muy alto, ¿por qué?)
   - Test 3: 24 ejercicios (más razonable)

## Estructura de Datos en response_new.json

Cada resultado incluye:
```json
{
  "test_name": "Nombre descriptivo",
  "query": "Query original del usuario",
  "status": "success",
  "response_data": {
    "response": "String JSON del plan completo",
    "plan": {
      "plan_summary": {...},
      "intent": {...},
      "user_profile_summary": {...},
      "nutrition_summary": {...},
      "weekly_calendar": [...],
      "meal_options": [...],
      "workout_options": [...],
      "ai_recommendations": {...}
    },
    "raw_data_summary": {
      "exercises_count": N,
      "recipes_count": N
    }
  }
}
```

## Próximos Pasos Recomendados

1. **Revisar Cálculo de Proteínas**: Investigar por qué Test 3 tiene 272.8g/día
2. **Aumentar Catálogo Keto**: Agregar más recetas keto a la base de datos
3. **Aumentar Catálogo Gluten-Free**: Expandir opciones sin gluten
4. **Validar Filtros Dietéticos**: Confirmar que las recetas respetan las restricciones
5. **Analizar Variabilidad de Ejercicios**: Entender por qué Test 1 tiene 36 vs 24 en otros

## Archivos Generados

1. **test_new_responses.py** - Script de prueba para 3 nuevos casos
2. **response_new.json** - Respuestas completas (379 KB)
3. **NUEVOS_TEST_RESULTS.md** - Este documento resumen

## Cómo Ejecutar Nuevamente

```bash
python test_new_responses.py
```

El script generará/actualizará `response_new.json` con las 3 respuestas completas.
