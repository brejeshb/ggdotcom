from fastapi import FastAPI
import uvicorn
import os
from dotenv import load_dotenv
import chromadb
import chromadb.server.fastapi

load_dotenv()

# Create the main FastAPI app
app = FastAPI()

# Create ChromaDB server
settings = chromadb.Settings(
    chroma_db_impl="duckdb+parquet",
    persist_directory="chroma_db",
    allow_reset=True,
    anonymized_telemetry=False
)

# Create and mount the ChromaDB API
api = chromadb.server.fastapi.FastAPI(settings=settings)
app.mount("/api", api.app)

@app.get("/")
async def root():
    return {"status": "healthy"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
