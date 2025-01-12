from fastapi import FastAPI, HTTPException
import uvicorn
import os
from dotenv import load_dotenv
import chromadb
from chromadb.config import Settings

load_dotenv()

app = FastAPI()

# Initialize ChromaDB client with proper settings
chroma_settings = Settings(
    chroma_api_impl="default",  # Set to default instead of rest
    allow_reset=True,
    is_persistent=True,
    persist_directory="chroma_db"
)

# Initialize ChromaDB client
chroma_client = chromadb.PersistentClient(
    path="chroma_db",
    settings=chroma_settings
)

@app.get("/")
async def root():
    return {"status": "healthy"}

@app.get("/collections")
async def list_collections():
    try:
        collections = chroma_client.list_collections()
        return {"collections": [col.name for col in collections]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v2/auth/identity")
async def get_identity():
    """Add identity endpoint to prevent 404 and provide basic identity info."""
    # You could return a more detailed identity object here, depending on your requirements
    return {"user": "default", "role": "guest", "permissions": ["read", "write"]}

@app.get("/health")
async def health_check():
    try:
        collections = chroma_client.list_collections()
        return {
            "status": "healthy",
            "collection_count": len(collections)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
