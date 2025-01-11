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

        if not self.collection_id:
            print("No valid collection ID available")
            return results

        try:
            # Get data directly from Firebase backup
            collection_data = self.firebase_backup.get_collection_details(self.collection_id)
            
            if collection_data and 'documents' in collection_data and collection_data['documents']:
                documents = collection_data['documents']
                print(f"Found {len(documents['documents'])} documents in collection")
                
                # Get the documents, distances (scores), and metadata
                matched_docs = []
                matched_scores = []
                matched_metadata = []
                
                for i, doc in enumerate(documents['documents']):
                    # Check if the document contains the place name
                    if place_name.lower() in doc.lower():
                        matched_docs.append(doc)
                        # Use metadata confidence if available
                        confidence = documents['metadatas'][i].get('confidence', 1.0) if documents.get('metadatas') else 1.0
                        matched_scores.append(confidence)
                        matched_metadata.append(documents['metadatas'][i] if documents.get('metadatas') else {})
                
                # Filter and sort results
                filtered_results = []
                for doc, score, metadata in zip(matched_docs, matched_scores, matched_metadata):
                    if score >= similarity_threshold:
                        if metadata.get("confidence", 1.0) < 0.5:
                            score *= 0.5  # Apply penalty for low confidence
                        filtered_results.append((doc, score))

                # Sort by score and take top results
                if filtered_results:
                    sorted_results = sorted(filtered_results, key=lambda x: x[1], reverse=True)
                    results["wikipedia"] = [doc for doc, _ in sorted_results[:limit]]
                else:
                    print("No matching documents found after filtering")
                    results["wikipedia"] = []
            else:
                print("No documents found in collection data")
                print(f"Collection data keys: {collection_data.keys() if collection_data else None}")
                results["wikipedia"] = []

        except Exception as e:
            print(f"Error querying collection: {str(e)}")
            results["wikipedia"] = []

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