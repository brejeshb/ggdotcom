from fastapi import FastAPI, HTTPException
import uvicorn
import os
from dotenv import load_dotenv
import chromadb.server.fastapi
from chromadb.config import Settings

load_dotenv()
app = FastAPI()

# Create the ChromaDB FastAPI app
chroma_app = chromadb.server.fastapi.FastAPI(
    settings=Settings(
        allow_reset=True,
        is_persistent=True,
        persist_directory="chroma_db"
    )
)

# Mount the ChromaDB app under the main app
app.mount("/api", chroma_app)

@app.get("/")
async def root():
    return {"status": "healthy"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
