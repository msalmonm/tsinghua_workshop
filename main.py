import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from elasticsearch import Elasticsearch
from openai import OpenAI

load_dotenv()

es_client = Elasticsearch(
    os.getenv('ELASTICSEARCH_URL'),
    api_key=os.getenv('ELASTICSEARCH_API_KEY')
)
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

app = FastAPI(title="Fitness RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class UserProfile(BaseModel):
    age: int
    sex: str
    weight_kg: float
    height_cm: float

class QueryRequest(BaseModel):
    query: str
    user_profile: UserProfile

modelo_texto = None

def cargar_modelo():
    """Carga el modelo y la librería solo cuando se recibe la primera petición"""
    global modelo_texto
    if modelo_texto is None:
        print("Descargando y cargando el modelo de texto...")
        # El import debe ir aquí adentro para que el servidor inicie al instante
        from sentence_transformers import SentenceTransformer
        modelo_texto = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    return modelo_texto

def search_elasticsearch(index_name: str, query_vector: list, k: int = 3):
    search_query = {
        "knn": {
            "field": "embedding",
            "query_vector": query_vector,
            "k": k,
            "num_candidates": 50
        },
        "_source": ["name", "search_context", "category"]
    }
    
    try:
        response = es_client.search(index=index_name, body=search_query)
        results = []
        for hit in response["hits"]["hits"]:
            results.append(hit["_source"])
        return results
    except Exception as e:
        print(f"Error buscando en {index_name}: {e}")
        return []

@app.get("/health")
def health_check():
    return {"status": "active", "message": "API is running"}

@app.post("/api/recommend")
def get_recommendation(request: QueryRequest):
    try:
        modelo_actual = cargar_modelo()
        query_vector = modelo_actual.encode(request.query).tolist()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error generando el vector de búsqueda.")

    exercises = search_elasticsearch("exercises", query_vector, k=3)
    recipes = search_elasticsearch("recipes", query_vector, k=3)

    context_text = "EJERCICIOS RECUPERADOS:\n"
    for ex in exercises:
        context_text += f"- {ex.get('search_context', '')}\n"
        
    context_text += "\nRECETAS RECUPERADAS:\n"
    for rec in recipes:
        context_text += f"- {rec.get('search_context', '')}\n"

    system_prompt = """
    Eres un entrenador personal y nutricionista experto. 
    Tu objetivo es crear un plan basado ÚNICAMENTE en los ejercicios y recetas proporcionados en el contexto.
    Habla en un tono motivador y claro. Formatea tu respuesta con Markdown (usa negritas y listas).
    """
    
    user_prompt = f"""
    Perfil del usuario: {request.user_profile.age} años, {request.user_profile.sex}, {request.user_profile.weight_kg}kg, {request.user_profile.height_cm}cm.
    Objetivo: {request.query}
    
    CONTEXTO DE LA BASE DE DATOS:
    {context_text}
    
    Por favor, genera una recomendación utilizando este contexto.
    """

    try:
        chat_completion = openai_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="gpt-4o-mini",
            temperature=0.7
        )
        final_response = chat_completion.choices[0].message.content
        
        return {
            "response": final_response,
            "raw_data": {
                "exercises": exercises,
                "recipes": recipes
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en OpenAI: {str(e)}")