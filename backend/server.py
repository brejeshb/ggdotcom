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

# Initialize ChromaDB server app
settings = Settings(
    persist_directory="chroma_db",
    allow_reset=True,
    is_persistent=True,
    anonymized_telemetry=False
)

# Create the ChromaDB API app correctly
api = chromadb.server.fastapi.FastAPI(settings=settings)

# Mount the ChromaDB app
app.mount("/api", api.app)  # Note the .app here

# Add health check endpoint
@app.get("/")
async def root():
    return {"status": "healthy"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
