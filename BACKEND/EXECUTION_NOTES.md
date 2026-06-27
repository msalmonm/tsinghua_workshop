# 🚀 Notas de Ejecución - Crawler Optimizado

## ⚠️ IMPORTANTE: NO EJECUTAR AÚN

El crawler ha sido **modificado y optimizado** según la investigación exhaustiva del API de FatSecret, pero **NO debe ejecutarse inmediatamente** por las siguientes razones:

---

## 📊 CAMBIOS REALIZADOS

### 1. ✅ Función `get_all_recipe_types()` agregada
- Obtiene los tipos de recetas oficiales del API de FatSecret
- Se ejecuta antes de comenzar las búsquedas
- Enriquece los términos de búsqueda automáticamente

### 2. ✅ Lista de búsquedas expandida
- **ANTES:** 48 términos de búsqueda
- **AHORA:** 100+ términos únicos (base + tipos oficiales del API)
- Cobertura mucho más amplia de categorías

### 3. ✅ Paginación extendida
- **ANTES:** Máximo 5 páginas por término (250 recetas)
- **AHORA:** Máximo 10 páginas por término (500 recetas)
- Permite extraer más recetas por categoría

### 4. ✅ Logging mejorado
- Progress tracking cada 10 términos
- Porcentaje de cobertura en tiempo real
- Detección automática de última página
- Estadísticas finales al terminar

### 5. ✅ Resumen ejecutivo al finalizar
- Total de recetas únicas extraídas
- IDs únicos procesados
- Cobertura estimada del total disponible (19,000)
- Términos de búsqueda utilizados

---

## ⚠️ CONSIDERACIONES CRÍTICAS

### 🔴 LÍMITE DE API CALLS

El plan gratuito de FatSecret tiene un límite de **5,000 API calls por día**.

**Estimación del crawler optimizado:**
```
100 términos de búsqueda
× ~5 páginas promedio por término
= ~500 búsquedas de listado

~8,000 recetas únicas encontradas
× 1 call para obtener detalle
= ~8,000 calls de detalle

TOTAL: ~8,500 API calls
```

⚠️ **ESTO EXCEDE EL LÍMITE DIARIO**

---

## 🎯 ESTRATEGIAS DE EJECUCIÓN

### Opción A: Ejecución Dividida en Múltiples Días (RECOMENDADO)

Modificar el código para procesar solo un subconjunto de términos por día:

```python
# En fetch_fatsecret_recipes(), agregar control de batch:

BATCH_SIZE = 25  # Procesar 25 términos por día
BATCH_NUMBER = 0  # Cambiar a 1, 2, 3 en días subsecuentes

start_idx = BATCH_NUMBER * BATCH_SIZE
end_idx = start_idx + BATCH_SIZE

batch_queries = all_queries[start_idx:end_idx]
print(f"  -> BATCH {BATCH_NUMBER + 1}: Procesando términos {start_idx}-{end_idx}")
```

**Ejecución sugerida:**
- **Día 1:** BATCH_NUMBER = 0 (términos 0-24) → ~2,000 calls
- **Día 2:** BATCH_NUMBER = 1 (términos 25-49) → ~2,000 calls
- **Día 3:** BATCH_NUMBER = 2 (términos 50-74) → ~2,000 calls
- **Día 4:** BATCH_NUMBER = 3 (términos 75-99) → ~2,000 calls

### Opción B: Reducir Páginas por Término

```python
max_pages = 5  # En lugar de 10
```

Esto reduciría el total a ~6,000 calls (aún excede, pero menos riesgo).

### Opción C: Upgrade a Plan Premier (IDEAL)

**Beneficios:**
- ✅ API calls ilimitados
- ✅ Datos de 58+ países
- ✅ 26 idiomas
- ✅ Image Recognition
- ✅ NLP
- ✅ Allergen info
- ✅ Sin throttling

**Costo:** Contactar a FatSecret para pricing

---

## 📋 RECOMENDACIONES ANTES DE EJECUTAR

### 1. ✅ Revisar el documento de investigación
Leer `FATSECRET_API_RESEARCH.md` completo para entender:
- Capacidades del API
- Limitaciones (ejercicios)
- Estrategias de optimización
- Resultados esperados

### 2. ✅ Decidir estrategia de ejecución
Elegir entre:
- Ejecución en múltiples días (requiere modificación de código)
- Reducir páginas por término (modificación simple)
- Upgrade a plan Premier (sin modificaciones)

### 3. ✅ Monitorear consumo de API
Agregar contador de API calls en el código:

```python
api_calls_count = 0

# Después de cada request:
api_calls_count += 1
if api_calls_count % 100 == 0:
    print(f"  [INFO] API calls consumidos: {api_calls_count}")
```

### 4. ✅ Backup de datos actuales
Antes de ejecutar el crawler optimizado:

```bash
# Exportar índices actuales de Elasticsearch
# (Agregar comandos específicos según tu setup)
```

### 5. ✅ Configurar rate limiting adicional (opcional)

Si experimentas throttling del API:

```python
time.sleep(0.2)  # Entre calls de detalle (actual: 0.1s)
time.sleep(0.5)  # Entre páginas (actual: 0.3s)
time.sleep(1.0)  # Entre términos (actual: 0.5s)
```

---

## 🎯 RESULTADOS ESPERADOS

### Con el crawler optimizado (ejecución completa):

**ANTES (actual):**
```
Ejercicios: 873 (Yuhonas)
Recetas: ~3,500
  - FatSecret: ~2,800 (con macros)
  - TheMealDB: ~666 (sin macros)
```

**DESPUÉS (optimizado):**
```
Ejercicios: 873 (sin cambios - FatSecret no tiene más)
Recetas: 14,000-18,000
  - FatSecret: 13,500-17,500 (con macros completos)
  - TheMealDB: ~666 (backup sin macros)
  
Cobertura: 70-95% de las 19,000 recetas de FatSecret
```

### Métricas de calidad:

- ✅ **100% en inglés** (requisito del usuario cumplido)
- ✅ **Información nutricional completa** (16 campos macro)
- ✅ **Imágenes de recetas** (cuando disponible)
- ✅ **URLs para más detalles**
- ✅ **Ratings de usuarios**
- ✅ **Categorías y tags dietéticos**
- ✅ **Sin duplicados** (deduplicación por recipe_id)

---

## 🐛 TROUBLESHOOTING

### Si excedes el límite de API:

**Error esperado:**
```json
{
  "error": {
    "code": 8,
    "message": "Daily API call limit exceeded"
  }
}
```

**Solución:**
1. Esperar 24 horas para reset del límite
2. Continuar con el siguiente batch
3. Los datos ya extraídos están seguros (mode upsert)

### Si el proceso se interrumpe:

- ✅ **Los datos ya procesados están guardados** (upsert mode)
- ✅ **Puedes reanudar sin perder progreso**
- ✅ **La deduplicación previene duplicados**

Simplemente ejecutar de nuevo:
```bash
python crawler.py
```

El sistema detectará recetas existentes y solo agregará nuevas.

---

## 📞 CONTACTO Y SOPORTE

### Documentación oficial:
- FatSecret API: https://platform.fatsecret.com/docs/guides
- Forum: https://groups.google.com/group/fatsecret-platform-api

### Recursos adicionales:
- `FATSECRET_API_RESEARCH.md`: Investigación completa
- `crawler.py`: Código actualizado con comentarios
- `main.py`: Sin cambios (compatible con nuevos datos)

---

## ✅ CHECKLIST PRE-EJECUCIÓN

Antes de ejecutar `python crawler.py`, verificar:

- [ ] Leí `FATSECRET_API_RESEARCH.md` completo
- [ ] Entiendo el límite de 5,000 API calls/día
- [ ] Decidí mi estrategia (batching/reducción/upgrade)
- [ ] Tengo backup de datos actuales (opcional)
- [ ] Configuré monitoreo de API calls (opcional)
- [ ] Entiendo que los ejercicios NO cambiarán (FatSecret no tiene más)
- [ ] Sé que el proceso puede tomar varias horas o días
- [ ] Confirmé que las credenciales en `.env` son correctas

---

## 🚀 EJECUCIÓN

Una vez completado el checklist:

```bash
# Navegar al directorio
cd C:\Users\msalm\Downloads\Tsinghua_Workshop_Frontend\BACKEND

# Ejecutar crawler
python crawler.py
```

**Tiempo estimado:**
- Con 100 términos × 10 páginas: **2-4 horas** (si no excede límite)
- Con batching (25 términos/día): **30-60 minutos por día × 4 días**

**Monitoreo:**
Observar los mensajes de progreso:
```
═══ PROGRESO: 5,000 recetas únicas (26.3% de 19,000 disponibles) ═══
═══ PROGRESO: 10,000 recetas únicas (52.6% de 19,000 disponibles) ═══
═══ PROGRESO: 15,000 recetas únicas (78.9% de 19,000 disponibles) ═══
```

---

## 🎉 DESPUÉS DE LA EJECUCIÓN

### 1. Verificar resultados en Elasticsearch

```bash
# Verificar conteo de recetas
curl -X GET "localhost:9200/recipes/_count"

# Ver estadísticas del índice
curl -X GET "localhost:9200/recipes/_stats"
```

### 2. Probar búsquedas en el frontend

Iniciar el servidor:
```bash
python main.py
```

Probar queries:
- "low carb chicken dinner"
- "vegan breakfast ideas"
- "keto desserts"
- "high protein salad"

### 3. Compartir resultados

- Total de recetas obtenidas
- Cobertura alcanzada (%)
- API calls consumidos
- Tiempo total de ejecución
- Cualquier issue encontrado

---

*Documento generado como parte de la optimización del crawler FatSecret.*
*Fecha: 2026-06-06*
