#!/usr/bin/env python3
"""
List available Hugging Face models for text generation
"""

import os
from dotenv import load_dotenv
import requests

load_dotenv()

HUGGINGFACE_API_KEY = os.getenv('HUGGINGFACE_API_KEY')

def list_popular_models():
    """List popular free text generation models on Hugging Face"""
    
    print("=" * 70)
    print("POPULAR FREE TEXT GENERATION MODELS ON HUGGING FACE")
    print("=" * 70)
    
    models = [
        {
            "name": "mistralai/Mistral-7B-Instruct-v0.2",
            "description": "7B parameter instruction-tuned model (CURRENT)",
            "size": "7B",
            "recommended": True
        },
        {
            "name": "google/flan-t5-large",
            "description": "780M parameter instruction-tuned model",
            "size": "780M",
            "recommended": False
        },
        {
            "name": "tiiuae/falcon-7b-instruct",
            "description": "7B parameter instruction-tuned model",
            "size": "7B",
            "recommended": False
        },
        {
            "name": "HuggingFaceH4/zephyr-7b-beta",
            "description": "7B parameter chat model",
            "size": "7B",
            "recommended": False
        },
        {
            "name": "meta-llama/Llama-2-7b-chat-hf",
            "description": "7B parameter chat model (requires approval)",
            "size": "7B",
            "recommended": False
        }
    ]
    
    for i, model in enumerate(models, 1):
        status = " ✓ CURRENT" if model["recommended"] else ""
        print(f"\n{i}. {model['name']}{status}")
        print(f"   Size: {model['size']}")
        print(f"   Description: {model['description']}")
    
    print("\n" + "=" * 70)
    print("NOTE: All models work with free Hugging Face API (with rate limits)")
    print("Get your API key at: https://huggingface.co/settings/tokens")
    print("=" * 70)

def test_current_model():
    """Test the currently configured model"""
    
    print("\n" + "=" * 70)
    print("TESTING CURRENT MODEL: mistralai/Mistral-7B-Instruct-v0.2")
    print("=" * 70)
    
    API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2"
    
    headers = {}
    if HUGGINGFACE_API_KEY:
        headers["Authorization"] = f"Bearer {HUGGINGFACE_API_KEY}"
        print("✓ Using API key from .env file")
    else:
        print("⚠ No API key found - using rate-limited public access")
    
    test_prompt = "What are the benefits of regular exercise?"
    
    payload = {
        "inputs": test_prompt,
        "parameters": {
            "max_new_tokens": 100,
            "temperature": 0.7
        }
    }
    
    try:
        print(f"\nSending test prompt: '{test_prompt}'")
        print("Waiting for response...")
        
        response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
        
        if response.status_code == 503:
            print("⚠ Model is loading, waiting 20 seconds...")
            import time
            time.sleep(20)
            response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
        
        response.raise_for_status()
        result = response.json()
        
        print("\n✓ Model is working!")
        print("\nResponse:")
        print("-" * 70)
        if isinstance(result, list) and len(result) > 0:
            print(result[0].get('generated_text', ''))
        elif isinstance(result, dict):
            print(result.get('generated_text', ''))
        else:
            print(result)
        print("-" * 70)
        
    except requests.exceptions.ConnectionError:
        print("\n✗ No internet connection")
        print("The system will use local fallback response generation")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("The system will use local fallback response generation")

if __name__ == "__main__":
    list_popular_models()
    test_current_model()
