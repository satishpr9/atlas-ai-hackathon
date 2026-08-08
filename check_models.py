import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("No API key found.")
else:
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        models = response.json().get('models', [])
        for m in models:
            if 'generateContent' in m.get('supportedGenerationMethods', []):
                print(f"Supported Model: {m['name']}")
    else:
        print(f"Error fetching models: {response.status_code} - {response.text}")
