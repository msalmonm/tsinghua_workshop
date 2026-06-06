# 📚 Índice de Documentación Completa

## 📖 Guía de Navegación por los Documentos

Esta es la documentación completa del proyecto **RAG Health & Fitness POC** desarrollado para el Tsinghua Workshop. A continuación se describe cada documento y su propósito.

---

## 🚀 Para Empezar Rápido

### 1. **README.md** ⭐ COMIENZA AQUÍ
**Propósito**: Quick start guide y vista general del proyecto
**Tiempo de lectura**: 5 minutos
**Contenido**:
- Instalación en 5 pasos
- Comandos básicos
- Estructura del proyecto
- Ejemplo de uso

**Cuándo leer**: Primer contacto con el proyecto

---

## 📊 Para Entender el Proyecto

### 2. **RESUMEN_EJECUTIVO.md** 💼
**Propósito**: Visión de alto nivel, arquitectura y valor del proyecto
**Tiempo de lectura**: 10 minutos
**Contenido**:
- Problema que resuelve
- Arquitectura en 3 capas
- Métricas de rendimiento
- Ventajas competitivas
- Potencial comercial

**Cuándo leer**: Para presentar el proyecto a stakeholders

---

### 3. **DOCUMENTACION_PROYECTO.md** 📘 DOCUMENTACIÓN MAESTRA
**Propósito**: Documentación técnica completa del sistema
**Tiempo de lectura**: 30-40 minutos
**Contenido**:
- Arquitectura detallada del sistema
- Requerimientos técnicos completos
- Documentación de todos los componentes
- Flujo de datos end-to-end
- Manejo de errores y edge cases
- Referencias a APIs y modelos

**Cuándo leer**: Para desarrollo, debugging o extensión del proyecto

**Secciones Principales**:
1. Visión General del Proyecto
2. Arquitectura del Sistema
3. Requerimientos Técnicos
4. Componentes Principales
   - main.py (Servidor API)
   - crawler.py (Sistema de Indexación)
   - query.py (Script CLI)
5. Flujo de Datos Completo
6. Guía de Uso
7. Integración con Tsinghua Workshop
8. Métricas y Performance
9. Futuras Mejoras

---

## 🔧 Para Desarrolladores

### 4. **DOCUMENTACION_MAIN.md** 🛠️
**Propósito**: Referencia técnica detallada de main.py
**Tiempo de lectura**: 15 minutos
**Contenido**:
- Modelos de datos (Pydantic)
- Todas las funciones documentadas
- Fórmulas y algoritmos
- Ejemplos de uso
- Parámetros y retornos

**Cuándo leer**: Al trabajar con el código de main.py

**Funciones Documentadas**:
- calculate_bmr()
- get_activity_factor()
- calculate_tdee()
- classify_goal()
- apply_goal_adjustment()
- detect_unsafe_goal()
- validate_nutrition_plan()
- search_elasticsearch()
- format_recipe_with_portions()
- get_recommendation() (endpoint principal)

---

### 5. **REQUERIMIENTOS.md** 📋
**Propósito**: Especificación funcional y técnica del sistema
**Tiempo de lectura**: 20 minutos
**Contenido**:
- Requerimientos funcionales (RF-001 a RF-015)
- Requerimientos no funcionales
- Criterios de aceptación
- Casos de uso detallados
- Validaciones y reglas de negocio

**Cuándo leer**: Para QA, testing o validación de features

**Requerimientos Clave**:
- RF-001: Búsqueda Semántica de Ejercicios
- RF-002: Búsqueda Semántica de Recetas
- RF-003: Cálculo de BMR
- RF-004: Cálculo de TDEE
- RF-005: Clasificación de Objetivos
- RF-006: Validación de Seguridad Nutricional
- RF-007: Cálculo de Macronutrientes
- RF-008: Generación de Plan con LLM

---

## 🎓 Para Contexto Académico

### 6. **INSTRUCTIVO_TSINGHUA.md** 🏫 MATERIAL DEL WORKSHOP
**Propósito**: Alineación con conceptos del Tsinghua Workshop
**Tiempo de lectura**: 25 minutos
**Contenido**:
- Objetivos de aprendizaje del workshop
- Explicación de materiales de referencia
- Implementación de conceptos teóricos
- Comparación antes/después del workshop
- Ejercicios propuestos resueltos
- Experimentos sugeridos

**Cuándo leer**: Para entender conexión con teoría académica

**Conceptos del Workshop Implementados**:
1. Vector Embeddings
2. kNN Search en Elasticsearch
3. Prompt Engineering
4. Hallucination Mitigation
5. RAG Pipeline completo

**Documentos del Workshop Analizados**:
- WIR-1.intro-IR(26.2.28).pdf
- LLM_and_Search_Report_Tsinghua_Expert_Expanded.pdf
- LLM_AND_SEARCH.pptx
- LLM_and_Search_Tsinghua.pptx

---

## 📁 Estructura Recomendada de Lectura

### Para Nuevos Usuarios
```
1. README.md (5 min)
   ↓
2. RESUMEN_EJECUTIVO.md (10 min)
   ↓
3. Probar la aplicación prácticamente
   ↓
4. DOCUMENTACION_PROYECTO.md (según necesidad)
```

### Para Desarrolladores
```
1. README.md (5 min)
   ↓
2. DOCUMENTACION_PROYECTO.md (30 min)
   ↓
3. DOCUMENTACION_MAIN.md (15 min)
   ↓
4. REQUERIMIENTOS.md (20 min)
   ↓
5. Explorar el código con contexto completo
```

### Para Académicos/Estudiantes
```
1. INSTRUCTIVO_TSINGHUA.md (25 min)
   ↓
2. RESUMEN_EJECUTIVO.md (10 min)
   ↓
3. DOCUMENTACION_PROYECTO.md (30 min)
   ↓
4. Analizar materiales en context_dump/
```

### Para Stakeholders/Management
```
1. RESUMEN_EJECUTIVO.md (10 min)
   ↓
2. README.md - sección de ejemplo (3 min)
   ↓
3. Demo en vivo
```

---

## 📊 Tabla Resumen de Documentos

| Documento | Propósito | Audiencia | Tiempo | Prioridad |
|-----------|-----------|-----------|---------|-----------|
| README.md | Quick start | Todos | 5 min | ⭐⭐⭐⭐⭐ |
| RESUMEN_EJECUTIVO.md | Visión ejecutiva | Management/Stakeholders | 10 min | ⭐⭐⭐⭐ |
| DOCUMENTACION_PROYECTO.md | Referencia técnica | Desarrolladores | 30 min | ⭐⭐⭐⭐⭐ |
| DOCUMENTACION_MAIN.md | Detalle de main.py | Desarrolladores | 15 min | ⭐⭐⭐ |
| REQUERIMIENTOS.md | Especificación | QA/Desarrolladores | 20 min | ⭐⭐⭐⭐ |
| INSTRUCTIVO_TSINGHUA.md | Contexto académico | Estudiantes/Académicos | 25 min | ⭐⭐⭐⭐ |
| INDICE_DOCUMENTACION.md | Navegación | Todos | 5 min | ⭐⭐⭐ |

---

## 🔍 Búsqueda Rápida por Temas

### Arquitectura
- RESUMEN_EJECUTIVO.md → Sección "Arquitectura en 3 Capas"
- DOCUMENTACION_PROYECTO.md → Sección "Arquitectura del Sistema"

### Instalación y Setup
- README.md → Sección "Quick Start"
- DOCUMENTACION_PROYECTO.md → Sección "Guía de Uso"

### Funciones y Código
- DOCUMENTACION_MAIN.md → Todas las funciones
- DOCUMENTACION_PROYECTO.md → Sección "Componentes Principales"

### Cálculos Metabólicos
- DOCUMENTACION_MAIN.md → Funciones calculate_bmr, calculate_tdee
- REQUERIMIENTOS.md → RF-003, RF-004, RF-007

### Búsqueda Vectorial
- INSTRUCTIVO_TSINGHUA.md → Concepto 1 y 2
- DOCUMENTACION_PROYECTO.md → search_elasticsearch()

### RAG Pipeline
- INSTRUCTIVO_TSINGHUA.md → Concepto 4
- DOCUMENTACION_PROYECTO.md → Sección "Flujo de Datos"
- RESUMEN_EJECUTIVO.md → "Arquitectura en 3 Capas"

### Seguridad Nutricional
- DOCUMENTACION_MAIN.md → detect_unsafe_goal()
- REQUERIMIENTOS.md → RF-006
- RESUMEN_EJECUTIVO.md → "Seguridad Nutricional"

### Mitigación de Alucinaciones
- INSTRUCTIVO_TSINGHUA.md → Concepto 4
- DOCUMENTACION_PROYECTO.md → "Manejo de Errores"

---

## 📦 Archivos del Proyecto

### Código Fuente
```
main.py         - Servidor FastAPI (API principal)
crawler.py      - Sistema de indexación
query.py        - Script CLI para testing
.env            - Variables de entorno (NO subir a Git)
.gitignore      - Archivos ignorados
```

### Documentación
```
README.md                     - Quick start guide
RESUMEN_EJECUTIVO.md         - Visión ejecutiva
DOCUMENTACION_PROYECTO.md    - Documentación maestra
DOCUMENTACION_MAIN.md        - Detalle de main.py
REQUERIMIENTOS.md            - Especificación funcional
INSTRUCTIVO_TSINGHUA.md      - Material académico
INDICE_DOCUMENTACION.md      - Este archivo
```

### Materiales del Workshop
```
context_dump/
├── LLM_AND_SEARCH.pptx
├── LLM_and_Search_Report_Tsinghua_Expert_Expanded.pdf
├── LLM_and_Search_Tsinghua.pptx
└── WIR-1.intro-IR(26.2.28).pdf
```

---

## ✅ Checklist de Documentación

### Para Desarrollador Nuevo
- [ ] Leer README.md
- [ ] Configurar .env
- [ ] Ejecutar crawler.py
- [ ] Probar query.py
- [ ] Iniciar servidor con main.py
- [ ] Leer DOCUMENTACION_PROYECTO.md
- [ ] Explorar DOCUMENTACION_MAIN.md según necesidad

### Para Presentación Académica
- [ ] Revisar materiales en context_dump/
- [ ] Leer INSTRUCTIVO_TSINGHUA.md completo
- [ ] Entender RESUMEN_EJECUTIVO.md
- [ ] Preparar demo en vivo
- [ ] Identificar conceptos del workshop aplicados

### Para Code Review
- [ ] Verificar REQUERIMIENTOS.md contra implementación
- [ ] Revisar todas las funciones en DOCUMENTACION_MAIN.md
- [ ] Validar manejo de errores en DOCUMENTACION_PROYECTO.md
- [ ] Comprobar tests contra criterios de aceptación

---

## 🎯 Objetivos de Esta Documentación

✅ **Onboarding rápido**: Cualquier persona puede empezar en < 15 minutos
✅ **Referencia técnica**: Desarrolladores encuentran respuestas sin leer código
✅ **Contexto académico**: Conexión clara con conceptos del workshop
✅ **Mantenibilidad**: Documentación actualizable y escalable
✅ **Múltiples audiencias**: Desde management hasta developers

---

## 📧 Ayuda y Soporte

Si después de revisar la documentación tienes preguntas:

1. **Problemas técnicos**: Consultar DOCUMENTACION_PROYECTO.md → "Manejo de Errores"
2. **Dudas de funciones**: Buscar en DOCUMENTACION_MAIN.md
3. **Conceptos del workshop**: Revisar INSTRUCTIVO_TSINGHUA.md
4. **Setup inicial**: Seguir README.md paso a paso

---

## 🔄 Mantenimiento de la Documentación

Esta documentación debe actualizarse cuando:
- Se agreguen nuevas funcionalidades
- Se cambien requerimientos
- Se refactorice código significativamente
- Se añadan nuevos endpoints
- Se integren nuevas APIs o servicios

**Última actualización**: Junio 2026
**Versión del proyecto**: 2.0.0
**Autor**: Proyecto Tsinghua Workshop

---

**💡 Tip**: Usa Ctrl+F (Cmd+F en Mac) para buscar términos específicos en cualquier documento. Todos están en formato Markdown para fácil navegación.
