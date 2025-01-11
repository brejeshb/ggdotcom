# server.py
from chromadb.config import Settings
import chromadb
from fastapi import FastAPI, HTTPException
import uvicorn
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Initialize ChromaDB with persistent storage
chroma_client = chromadb.PersistentClient(
    path="chroma_db",
    settings=Settings(
        allow_reset=True,
        is_persistent=True
    )
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

@app.get("/health")
async def health_check():
    try:
        # Test basic ChromaDB operations
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
