import os
from dotenv import load_dotenv

load_dotenv()

CHROMA_HOST = os.getenv('CHROMA_HOST', 'https://ggdotcom-chromadb.onrender.com')
CHROMA_PORT = int(os.getenv('CHROMA_PORT', 8000))
CHROMA_API_KEY = os.getenv('CHROMA_API_KEY', '')
CHROMA_SSL = os.getenv('CHROMA_SSL', 'false').lower() == 'true'
FIREBASE_BUCKET = "ggdotcom-254aa.firebasestorage.app"

def get_firebase_backup():
    """Get Firebase Storage backup settings"""
    return {
        "bucket_name": FIREBASE_BUCKET,
        "base_path": "ggdotcom/chromadb"
    }

def get_chroma_settings():
    return {
        "chroma_host": CHROMA_HOST,
        "chroma_port": CHROMA_PORT,
        "chroma_ssl": CHROMA_SSL,
        "chroma_api_key": CHROMA_API_KEY,
        "allow_reset": True,
        "firebase_backup": get_firebase_backup()
    }