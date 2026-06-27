# ✅ LISTO PARA EJECUTAR - Crawler Priorizado y Reanudable

## 🎯 Cambios Implementados

### 1. ✅ PRIORIZACIÓN INTELIGENTE
Las categorías más útiles para tu RAG se procesan **primero**:

**Orden de ejecución:**
```
TIER 1 🥇: Proteínas principales (chicken, beef, salmon, turkey, shrimp, fish, tuna, pork)
TIER 2 🥈: Estilos populares (salad, soup, pasta, breakfast, healthy, low carb, high protein, keto)
TIER 3 🥉: Dietas (vegetarian, vegan, gluten free, dairy free, low fat, low sodium)
TIER 4: Internacional (mexican, italian, asian, chinese, thai, indian, greek, mediterranean)
TIER 5: Técnicas (slow cooker, instant pot, air fryer, one pot, casserole, stir fry)
TIER 6: Ingredientes (rice, potato, quinoa, beans, lentils, tofu, mushroom)
TIER 7: Postres (cake, cookies, bread, muffin, brownie, pie, dessert, pizza)
TIER 8: Adicionales (curry, stew, sandwich, burger, wrap, smoothie, juice, noodles)
```

**Beneficio:** Si llegas al límite de API, ya tendrás las categorías más importantes.

---

### 2. ✅ SISTEMA DE PROGRESO REANUDABLE

**Archivo generado:** `crawler_progress.json`

**Qué hace:**
- Guarda automáticamente cada 5 términos procesados
- Detecta cuando excedes el límite de API
- Mañana continúa exactamente donde se detuvo

**Ejemplo de crawler_progress.json:**
```json
{
  "processed_queries": [
    "chicken",
    "beef",
    "salmon",
    "turkey",
    "shrimp"
  ],
  "last_run": "2026-06-06 14:30:00"
}
```

---

### 3. ✅ DETECCIÓN AUTOMÁTICA DE LÍMITE

**El crawler detecta automáticamente:**
- Error 429 (Too Many Requests)
- Mensajes con "limit" o "exceeded"

**Cuando detecta el límite:**
```
⚠️ LÍMITE DE API ALCANZADO
📊 Recetas extraídas antes del límite: 3,245
💾 Guardando progreso...
✓ Progreso guardado en 'crawler_progress.json'

💡 MAÑANA: Ejecuta de nuevo 'python crawler.py' para continuar
🔄 Se reanudará desde: 'keto' (término 9 de 75)
```

---

## 🚀 CÓMO USAR

### Hoy (Primera ejecución):
```bash
cd C:\Users\msalm\Downloads\Tsinghua_Workshop_Frontend\BACKEND
python crawler.py
```

**Lo que pasará:**
1. Procesará TheMealDB (666 recetas) ✓
2. Procesará Ejercicios (873) ✓
3. Comenzará con FatSecret desde **chicken** (prioridad máxima)
4. Extraerá hasta que llegue al límite de API
5. Guardará progreso automáticamente
6. Te dirá desde dónde continuar mañana

**Tiempo estimado:** 1-2 horas hasta que llegue al límite

### Mañana (Continuar):
```bash
python crawler.py
```

**Lo que pasará:**
1. Detectará `crawler_progress.json`
2. Mostrará: "📂 Progreso anterior encontrado: 8 términos ya procesados"
3. **Saltará los términos ya procesados**
4. Continuará desde donde se quedó
5. Extraerá hasta llegar de nuevo al límite o terminar

**Repetir:** Cada día ejecutar `python crawler.py` hasta completar todo

---

## 📊 OUTPUT ESPERADO

### Al iniciar:
```
[3/3] Buscando recetas en FatSecret (Modo Extracción Profunda)...
✓ Autenticación en FatSecret exitosa.
-> Obteniendo tipos de recetas oficiales del API...
✓ 12 tipos oficiales obtenidos: Appetizers, Soups, Main Dishes...

═══════════════════════════════════════════════════════════
🎯 MODO PRIORIZADO + REANUDABLE
═══════════════════════════════════════════════════════════
• Total de términos disponibles: 75
• Ya procesados: 0
• Pendientes: 75
• Objetivo: Maximizar cobertura de 19,000+ recetas
═══════════════════════════════════════════════════════════

🚀 INICIANDO extracción con términos priorizados...
📊 Orden: Proteínas → Estilos → Dietas → Internacional → Técnicas → Ingredientes → Postres

  -> [1/75] 🎯 'chicken' - Página 0: 50 recetas...
     ↳ Página 1: 50 recetas...
     ↳ Página 2: 50 recetas...
     ↳ Página 3: 50 recetas...
     ↳ Página 4: 50 recetas...
     ↳ Página 5: 50 recetas...
     ↳ Página 6: 50 recetas...
  -> [2/75] 🎯 'beef' - Página 0: 50 recetas...
     ...
  ═══ PROGRESO: 1,200 recetas únicas (6.3% de 19,000 disponibles) ═══
  💾 Progreso guardado: 5 términos completados
```

### Si alcanza el límite:
```
⚠️ LÍMITE DE API ALCANZADO
📊 Recetas extraídas antes del límite: 3,245
💾 Guardando progreso...
✓ Progreso guardado en 'crawler_progress.json'

💡 MAÑANA: Ejecuta de nuevo 'python crawler.py' para continuar
🔄 Se reanudará desde: 'vegetarian' (término 11 de 75)
```

### Al reanudar (día siguiente):
```
[3/3] Buscando recetas en FatSecret (Modo Extracción Profunda)...
📂 Progreso anterior encontrado: 10 términos ya procesados
📅 Última ejecución: 2026-06-06 14:30:00
✓ Autenticación en FatSecret exitosa.

═══════════════════════════════════════════════════════════
🎯 MODO PRIORIZADO + REANUDABLE
═══════════════════════════════════════════════════════════
• Total de términos disponibles: 75
• Ya procesados: 10
• Pendientes: 65
• Objetivo: Maximizar cobertura de 19,000+ recetas
═══════════════════════════════════════════════════════════

🚀 INICIANDO extracción con términos priorizados...

  -> [1/65] 🎯 'vegetarian' - Página 0: 50 recetas...
     ...
```

### Al terminar todo:
```
═══════════════════════════════════════════════════════════
✓ EXTRACCIÓN COMPLETADA
═══════════════════════════════════════════════════════════
• Recetas únicas extraídas: 8,234
• IDs únicos procesados: 8,234
• Cobertura estimada: 43.3% de 19,000 disponibles
• Términos procesados (esta sesión): 65
• Términos procesados (total): 75
• Términos restantes: 0
💾 Progreso guardado en 'crawler_progress.json'
═══════════════════════════════════════════════════════════

🎉 ¡COMPLETADO! Todos los términos fueron procesados
💡 Para reiniciar desde cero, elimina 'crawler_progress.json'
```

---

## 🔧 COMANDOS ÚTILES

### Ver progreso actual:
```bash
type crawler_progress.json
```

### Reiniciar desde cero:
```bash
del crawler_progress.json
python crawler.py
```

### Ver cuántas recetas tienes en Elasticsearch:
```bash
curl -X GET "localhost:9200/recipes/_count"
```

---

## 📊 RESULTADOS ESPERADOS

### Por día (estimado):
- **Día 1:** ~10-15 términos → 2,000-3,000 recetas
- **Día 2:** ~10-15 términos → 2,000-3,000 recetas más
- **Día 3:** ~10-15 términos → 2,000-3,000 recetas más
- **Día 4:** ~10-15 términos → 2,000-3,000 recetas más
- **Día 5:** ~10-15 términos → 1,000-2,000 recetas más

**Total esperado:** 10,000-14,000 recetas únicas de FatSecret

### Con MealDB incluido:
- FatSecret: 10,000-14,000 (con macros completos)
- TheMealDB: 666 (sin macros, backup)
- **TOTAL: 10,666-14,666 recetas** (vs 3,609 actuales)

**Mejora:** **3-4x más recetas** 🚀

---

## ⚠️ NOTAS IMPORTANTES

### ✅ Datos seguros
- El modo upsert **NO sobrescribe** datos existentes
- Solo agrega recetas nuevas
- Los 873 ejercicios permanecen intactos

### ✅ Prioridad correcta
- Las categorías más útiles (chicken, beef, salad) van **primero**
- Si solo completas el Día 1, ya tendrás lo más importante

### ✅ Reanudación inteligente
- Puedes detener el crawler con Ctrl+C en cualquier momento
- El progreso se guarda cada 5 términos
- Al reanudar, **no repite** términos ya procesados

### ✅ Todo en inglés
- FatSecret devuelve data en inglés por defecto ✓
- El usuario siempre verá recetas en inglés

---

## 🎯 AHORA SÍ: ¡A EJECUTAR!

```bash
cd C:\Users\msalm\Downloads\Tsinghua_Workshop_Frontend\BACKEND
python crawler.py
```

**Tiempo de ejecución:** 1-2 horas hoy, luego mañana continúa automáticamente.

**Monitorea el output** para ver el progreso en tiempo real. Cuando veas el mensaje de límite alcanzado, simplemente déjalo y ejecuta mañana de nuevo.

---

*Crawler optimizado, priorizado y reanudable - Listo para maximizar extracción de FatSecret.*
*Fecha: 2026-06-06*
