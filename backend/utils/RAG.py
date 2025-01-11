# rag_service.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import chromadb
from datetime import datetime, timedelta
from collections import defaultdict
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from backend.config import get_chroma_settings

app = Flask(__name__)
CORS(app)

class RAGManager:
    def __init__(self):
        settings = get_chroma_settings()
        self.client = chromadb.HttpClient(
            host=settings["chroma_host"],
            port=settings["chroma_port"],
            ssl=settings["chroma_ssl"],
            headers={"X-Api-Key": settings["chroma_api_key"]} if settings["chroma_api_key"] else None
        )
        self.collections = {}
        self.initialize_collections()

    def initialize_collections(self):
        """Initialize available collections"""
        try:
            self.collections["wikipedia"] = self.client.get_collection("wikipedia_collection")
            # Add other collections here as needed
        except Exception as e:
            print(f"Error initializing collections: {str(e)}")

    def query_place(self, place_name: str, limit: int = 3) -> dict:
        """Query all collections for place information"""
        results = {}
        
        for source, collection in self.collections.items():
            try:
                query_result = collection.query(
                    query_texts=[place_name],
                    n_results=limit
                )
                
                if query_result and query_result['documents']:
                    results[source] = query_result['documents'][0]
                else:
                    results[source] = []
                    
            except Exception as e:
                print(f"Error querying {source}: {str(e)}")
                results[source] = []
        
        return results

# Initialize RAG manager
rag_manager = RAGManager()

@app.route('/RAG', methods=['POST'])
def query_location():
    try:
        data = request.get_json()
        place_name = data.get('place_name')
        limit = data.get('limit', 3)
        
        if not place_name:
            return jsonify({'error': 'No place name provided'}), 400
            
        results = rag_manager.query_place(place_name, limit)
        return jsonify(results)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10001))
    app.run(host="0.0.0.0", port=port)