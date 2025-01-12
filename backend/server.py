from fastapi import FastAPI
import uvicorn
import os
from dotenv import load_dotenv
import chromadb
from chromadb.server import ChromaAPIServer

load_dotenv()

# Create the main FastAPI app
app = FastAPI()

# Create ChromaDB server
chroma_server = ChromaAPIServer(
    settings=chromadb.Settings(
        is_persistent=True,
        persist_directory="chroma_db",
        allow_reset=True,
        anonymized_telemetry=False
    )
)

# Mount ChromaDB server at /api endpoint
app.mount("/api", chroma_server.app)

@app.get("/")
async def root():
    return {"status": "healthy"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
