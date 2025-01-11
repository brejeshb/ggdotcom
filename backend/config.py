import os
from dotenv import load_dotenv

load_dotenv()

CHROMA_HOST = os.getenv('CHROMA_HOST', 'https://ggdotcom-chromadb.onrender.com')
CHROMA_PORT = int(os.getenv('CHROMA_PORT', 8000))
CHROMA_API_KEY = os.getenv('CHROMA_API_KEY', '')
CHROMA_SSL = os.getenv('CHROMA_SSL', 'false').lower() == 'true'

def get_chroma_settings():
    return {
        "chroma_host": os.getenv("CHROMA_HOST"),
        "chroma_port": int(os.getenv("CHROMA_PORT", "8000")),
        "chroma_ssl": os.getenv("CHROMA_SSL", "true").lower() == "true",
        "chroma_api_key": os.getenv("CHROMA_API_KEY"),
        "persist_directory": "./chroma_db",
        "allow_reset": True
    }
