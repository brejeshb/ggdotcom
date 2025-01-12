from fastapi import FastAPI, HTTPException
import uvicorn
import os
from dotenv import load_dotenv
import chromadb.server.fastapi

load_dotenv()

# Create the ChromaDB API app with the new configuration style
chroma_api = chromadb.server.fastapi.FastAPI(
    settings=chromadb.config.Settings(
        persist_directory="chroma_db",
        allow_reset=True,
        is_persistent=True,
        anonymized_telemetry=False  # Optional, add if you want to disable telemetry
    )
)

# Create the main FastAPI app
app = FastAPI()

# Mount the ChromaDB app at the root path
# This ensures all ChromaDB endpoints are available
app.mount("/api", chroma_api)

# Add custom health check endpoint
@app.get("/")
async def root():
    return {"status": "healthy"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
