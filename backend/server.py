from fastapi import FastAPI, HTTPException
import uvicorn
import os
from dotenv import load_dotenv
import chromadb
from chromadb.config import Settings

load_dotenv()

app = FastAPI()

# Initialize ChromaDB with REST implementation
chroma_settings = Settings(
    chroma_api_impl="rest",  # This is crucial
    allow_reset=True,
    persist_directory="chroma_db"
)

# Use HttpClient instead of PersistentClient for the server
chroma_client = chromadb.HttpClient(
    host="localhost",  # Since this is running on Railway itself
    port=8000,
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
    return {"user": "default"}

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
