import os
from dotenv import load_dotenv

load_dotenv()

CHROMA_HOST = 'ggdotcom-production.up.railway.app'
CHROMA_PORT = 443  # HTTPS port
CHROMA_API_KEY = os.getenv('CHROMA_API_KEY', '')
CHROMA_SSL = True
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
        "chroma_api_version": "v1",  # Add this line
        "allow_reset": True,
        "firebase_backup": get_firebase_backup()
    }
