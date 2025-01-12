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

# Create ChromaDB server with updated configuration
settings = Settings(
    is_persistent=True,
    persist_directory="chroma_db",
    anonymized_telemetry=False,
    allow_reset=True,
    api_impl="rest",
    server_host="0.0.0.0",
    server_port=int(os.getenv("PORT", 8000))
)

# Create and mount the ChromaDB API
api = chromadb.Server(settings)
app.mount("/api", api.app)

@app.get("/")
async def root():
    return {"status": "healthy"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
