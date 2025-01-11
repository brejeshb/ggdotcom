import os
from dotenv import load_dotenv

load_dotenv()

CHROMA_HOST = os.getenv('CHROMA_HOST', 'http://localhost:8000')
CHROMA_PORT = int(os.getenv('CHROMA_PORT', 8000))
CHROMA_API_KEY = os.getenv('CHROMA_API_KEY', '')
CHROMA_SSL = os.getenv('CHROMA_SSL', 'false').lower() == 'true'

def get_chroma_settings():
    return {
        "chroma_host": CHROMA_HOST,
        "chroma_port": CHROMA_PORT,
        "chroma_api_key": CHROMA_API_KEY,
        "chroma_ssl": CHROMA_SSL
    }