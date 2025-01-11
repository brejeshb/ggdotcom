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
        self.collection_id = None  # Will store the active collection ID
        self.initialize_collections()

    def initialize_collections(self):
        """Initialize by finding available collections in Firebase"""
        try:
            # First try to get collection from ChromaDB
            self.collections["wikipedia"] = self.client.get_collection("wikipedia_collection")
            print("Successfully initialized ChromaDB collection")
        except Exception as e:
            print(f"ChromaDB collection error: {str(e)}")
            print("Attempting to restore from Firebase backup...")
            
            # List available collections in Firebase
            available_collections = self.firebase_backup.list_firebase_collections()
            print("Available collections in Firebase:", available_collections)
            
            if available_collections:
                # Use the first available collection
                self.collection_id = available_collections[0]
                print(f"Using collection ID: {self.collection_id}")
            else:
                print("No collections found in Firebase")
                self.collection_id = None

    def query_place(self, place_name: str, limit: int = 3, similarity_threshold: float = 0.5) -> dict:
        """Query collections and penalize irrelevant results based on similarity score."""
        results = {}

        for source, collection in self.collections.items():
            try:
                # Try ChromaDB collection first
                query_result = collection.query(
                    query_texts=[place_name],
                    n_results=limit
                )
                
                if query_result and query_result['documents']:
                    filtered_documents = []
                    filtered_scores = []
                    
                    for doc, score, metadata in zip(query_result['documents'][0], 
                                                  query_result['distances'][0], 
                                                  query_result['metadatas'][0]):
                        if score >= similarity_threshold:
                            if metadata.get("confidence", 1.0) < 0.5:
                                score *= 0.5
                            filtered_documents.append(doc)
                            filtered_scores.append(score)
                    
                    if filtered_documents:
                        sorted_docs = sorted(zip(filtered_documents, filtered_scores), 
                                          key=lambda x: x[1], reverse=True)
                        results[source] = [doc for doc, _ in sorted_docs[:limit]]
                    else:
                        results[source] = []
                        
            except Exception as e:
                print(f"Error querying ChromaDB collection: {str(e)}")
                print("Falling back to Firebase backup...")
                
                try:
                    # Fallback to Firebase backup
                    if self.collection_id:
                        backup_data = self.firebase_backup.load_collection(self.collection_id)
                        if backup_data:
                            # Simple text matching fallback
                            matched_docs = []
                            for doc in backup_data.get('documents', []):
                                if place_name.lower() in doc.lower():
                                    matched_docs.append(doc)
                            results[source] = matched_docs[:limit]
                            
                except Exception as backup_error:
                    print(f"Error querying Firebase backup: {str(backup_error)}")
                    results[source] = []

        return results
# Create a single instance to be imported
rag_manager = RAGManager()

# Only run Flask app if this file is run directly
if __name__ == '__main__':
    app = Flask(__name__)
    CORS(app)

    @app.route('/chromadb', defaults={'path': ''})
    @app.route('/chromadb<path:path>', methods=['HEAD'])
    def ping(path):
        try:
            # Check ChromaDB connectivity
            rag_manager.client.heartbeat()
            return '', 200
        except Exception as e:
            app.logger.error(f"Health check failed: {str(e)}")
            return '', 503

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