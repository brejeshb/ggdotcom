from fastapi import FastAPI
import uvicorn
import os
from dotenv import load_dotenv
import chromadb
from chromadb.config import Settings
import chromadb.server.fastapi

load_dotenv()

# Create the main FastAPI app
app = FastAPI()

# Initialize ChromaDB server app with settings
settings = Settings(
    chroma_api_impl="rest",
    chroma_server_host="0.0.0.0",
    chroma_server_http_port=8000,
    persist_directory="chroma_db",
    allow_reset=True,
    is_persistent=True,
    anonymized_telemetry=False
)

# Create and mount the ChromaDB API
api = chromadb.server.fastapi.FastAPI(settings=settings)
app.mount("/api/v1", api.app)  # Mount at v1 endpoint

@app.get("/")
async def root():
    return {"status": "healthy"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
