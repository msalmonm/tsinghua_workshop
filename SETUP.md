# RAG Health & Fitness Engine - Setup Guide

## Requisitos Previos

- Node.js 18+ instalado
- Python 3.10+ instalado
- Cuenta de Elastic Cloud (prueba gratuita de 14 días)
- API key de Google Gemini (gratuita)

## Paso 1: Configurar Elasticsearch

### 1.1 Crear cuenta en Elastic Cloud

1. Ve a https://cloud.elastic.co/registration
2. Crea una cuenta gratuita
3. Inicia una prueba de 14 días

### 1.2 Crear un deployment

1. Haz clic en "Create deployment"
2. Selecciona la región más cercana a ti
3. Usa la configuración por defecto (suficiente para el proyecto)
4. Guarda las credenciales que te muestra (las necesitarás después)

### 1.3 Obtener la URL y API Key

**Opción A: Usar Cloud ID (recomendado)**
1. En tu deployment, copia el "Cloud ID"
2. La URL será: `https://[tu-cloud-id].es.[region].gcp.cloud.es.io:443`

**Opción B: Obtener endpoint directo**
1. Ve a tu deployment
2. Copia el "Elasticsearch endpoint"

**Crear API Key:**
1. Ve a Stack Management > API Keys
2. Haz clic en "Create API key"
3. Dale un nombre (ej: "rag-fitness-app")
4. Copia la API key (solo se muestra una vez)

## Paso 2: Configurar Google Gemini API

### 2.1 Obtener API Key

1. Ve a https://makersuite.google.com/app/apikey
2. Inicia sesión con tu cuenta de Google
3. Haz clic en "Create API Key"
4. Selecciona un proyecto o crea uno nuevo
5. Copia la API key generada

**Nota:** La API de Gemini tiene un tier gratuito generoso que es suficiente para este proyecto.

## Paso 3: Configurar Variables de Entorno

### 3.1 Crear archivo .env.local

```bash
# En Windows (PowerShell)
Copy-Item .env.example .env.local

# En Windows (CMD)
copy .env.example .env.local

# En Linux/Mac
cp .env.example .env.local
```

### 3.2 Editar .env.local

Abre el archivo `.env.local` y completa con tus valores reales:

```env
ELASTICSEARCH_URL=https://tu-deployment.es.us-central1.gcp.cloud.es.io:443
ELASTICSEARCH_API_KEY=tu_api_key_de_elasticsearch_aqui
GOOGLE_GEMINI_API_KEY=tu_api_key_de_gemini_aqui
NODE_ENV=development
```

**⚠️ IMPORTANTE:** 
- Nunca compartas este archivo
- Nunca lo subas a Git (ya está en .gitignore)
- Guarda una copia segura de tus API keys

## Paso 4: Instalar Dependencias

### 4.1 Dependencias de Node.js

```bash
npm install
```

### 4.2 Dependencias de Python (para scripts de ingestion)

```bash
# Crear entorno virtual (recomendado)
python -m venv venv

# Activar entorno virtual
# En Windows:
venv\Scripts\activate
# En Linux/Mac:
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

## Paso 5: Verificar Configuración

### 5.1 Probar conexión a Elasticsearch

Crea un archivo de prueba `test-es.js`:

```javascript
const { Client } = require('@elastic/elasticsearch');

const client = new Client({
  node: process.env.ELASTICSEARCH_URL,
  auth: {
    apiKey: process.env.ELASTICSEARCH_API_KEY
  }
});

async function testConnection() {
  try {
    const info = await client.info();
    console.log('✅ Conexión exitosa a Elasticsearch');
    console.log('Versión:', info.version.number);
  } catch (error) {
    console.error('❌ Error conectando a Elasticsearch:', error.message);
  }
}

testConnection();
```

Ejecutar:
```bash
node -r dotenv/config test-es.js
```

### 5.2 Probar API de Gemini

Crea un archivo de prueba `test-gemini.js`:

```javascript
const { GoogleGenerativeAI } = require('@google/generative-ai');

const genAI = new GoogleGenerativeAI(process.env.GOOGLE_GEMINI_API_KEY);

async function testGemini() {
  try {
    const model = genAI.getGenerativeModel({ model: 'gemini-1.5-flash' });
    const result = await model.generateContent('Hello!');
    console.log('✅ Conexión exitosa a Gemini API');
    console.log('Respuesta:', result.response.text());
  } catch (error) {
    console.error('❌ Error conectando a Gemini:', error.message);
  }
}

testGemini();
```

Ejecutar:
```bash
node -r dotenv/config test-gemini.js
```

## Paso 6: Ejecutar Scripts de Ingestion

### 6.1 Ingerir datos de ejercicios

```bash
# Activar entorno virtual de Python
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Ejecutar script
python scripts/ingest_exercises.py
```

### 6.2 Ingerir datos de recetas

```bash
python scripts/ingest_recipes.py
```

**Nota:** Estos scripts pueden tardar varios minutos. Verás el progreso en la consola.

## Paso 7: Ejecutar la Aplicación

### 7.1 Modo desarrollo

```bash
npm run dev
```

La aplicación estará disponible en: http://localhost:3000

### 7.2 Verificar funcionamiento

1. Abre http://localhost:3000 en tu navegador
2. Completa el formulario con tus datos
3. Envía y espera la generación del plan
4. Deberías ver el plan aparecer en tiempo real

## Solución de Problemas

### Error: "ELASTICSEARCH_URL is not defined"

- Verifica que el archivo `.env.local` existe
- Verifica que las variables están correctamente escritas
- Reinicia el servidor de desarrollo

### Error: "Connection refused" al conectar a Elasticsearch

- Verifica que la URL de Elasticsearch es correcta
- Verifica que tu deployment está activo en Elastic Cloud
- Verifica que la API key es válida

### Error: "Invalid API key" con Gemini

- Verifica que copiaste la API key completa
- Verifica que la API key no tiene espacios al inicio o final
- Genera una nueva API key si es necesario

### Error: "Index not found" al hacer búsquedas

- Ejecuta primero los scripts de ingestion
- Verifica que los scripts completaron exitosamente
- Verifica los logs de los scripts para errores

### Los scripts de ingestion son muy lentos

- Reduce `MAX_EXERCISES` y `MAX_RECIPES` en `.env.local`
- Aumenta `BULK_BATCH_SIZE` (cuidado con límites de memoria)
- Verifica tu conexión a internet

## Recursos Adicionales

- [Documentación de Elasticsearch](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html)
- [Documentación de Google Gemini](https://ai.google.dev/docs)
- [Documentación de Next.js](https://nextjs.org/docs)
- [Documentación de @xenova/transformers](https://huggingface.co/docs/transformers.js)

## Contacto y Soporte

Si encuentras problemas durante la configuración, revisa:
1. Los logs de la consola
2. Los mensajes de error específicos
3. La documentación de cada servicio

¡Buena suerte con tu proyecto! 🚀
