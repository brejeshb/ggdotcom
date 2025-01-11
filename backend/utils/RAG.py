# RAG.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import chromadb
from datetime import datetime, timedelta
from collections import defaultdict
import sys
import os
import json
from typing import Dict, List
from utils.firebase_backup import FirebaseBackup

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from backend.config import get_chroma_settings, get_firebase_backup

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
        self.firebase_backup = FirebaseBackup(settings["firebase_backup"]["bucket_name"])
        self.initialize_collections()

    def initialize_collections(self):
        """Initialize collections, falling back to Firebase backup if needed"""
        try:
            # Try to get collection from ChromaDB
            self.collections["wikipedia"] = self.client.get_collection("wikipedia_collection")
            print("Successfully initialized ChromaDB collection")
        except Exception as e:
            print(f"ChromaDB collection error: {str(e)}")
            print("Attempting to restore from Firebase backup...")
            self._restore_from_backup("wikipedia_collection")

    def query_place(self, place_name: str, limit: int = 3, similarity_threshold: float = 0.5) -> dict:
        """Query collections and penalize irrelevant results based on similarity score and return empty if no relevant results."""
        results = {}

        if not self.collection_id:
            print("No valid collection ID available")
            return results

        try:
            # Load the collection data directly from Firebase
            collection_data = self.firebase_backup.load_collection(self.collection_id)
            
            if collection_data and collection_data.get('documents'):
                documents = collection_data['documents']
                scores = collection_data.get('distances', [])  # Similarity scores
                metadatas = collection_data.get('metadatas', [])  # Metadata if available

                # Filter documents by similarity score threshold
                filtered_documents = []
                filtered_scores = []
                
                for doc, score, metadata in zip(documents, scores, metadatas):
                    if score >= similarity_threshold:
                        # Optional: Penalize based on metadata, e.g., low confidence
                        if metadata.get("confidence", 1.0) < 0.5:
                            score *= 0.5  # Apply penalty for low confidence
                        filtered_documents.append(doc)
                        filtered_scores.append(score)

                # Check if any relevant documents passed the threshold
                if filtered_documents:
                    # Re-rank the filtered documents based on their final scores
                    sorted_docs = sorted(zip(filtered_documents, filtered_scores), 
                                    key=lambda x: x[1], reverse=True)
                    results["wikipedia"] = [doc for doc, _ in sorted_docs[:limit]]
                else:
                    # Fallback to simple text matching if no documents pass the threshold
                    matched_docs = [
                        doc for doc in documents
                        if place_name.lower() in doc.lower()
                    ]
                    if matched_docs:
                        results["wikipedia"] = matched_docs[:limit]
                    else:
                        results["wikipedia"] = []  # No documents found
                        
            else:
                # No data found in collection
                print(f"Available keys in collection data: {collection_data.keys() if collection_data else None}")
                results["wikipedia"] = []

        except Exception as e:
            print(f"Error querying collection: {str(e)}")
            print(f"Collection data structure: {collection_data.keys() if collection_data else None}")
            results["wikipedia"] = []

        return results
# Create a single instance to be imported
rag_manager = RAGManager()

# Only run Flask app if this file is run directly
if __name__ == '__main__':
    app = Flask(__name__)
    CORS(app)

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

    port = int(os.environ.get("PORT", 10001))
    app.run(host="0.0.0.0", port=port)