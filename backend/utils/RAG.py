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
from firebase_backup import FirebaseBackup
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

    def _restore_from_backup(self, collection_name: str):
        """Restore collection from Firebase backup"""
        try:
            backup_data = self.firebase_backup.load_collection(collection_name)
            if backup_data and all(key in backup_data for key in ['documents', 'embeddings', 'metadatas', 'ids']):
                collection = self.client.create_collection(collection_name)
                collection.add(
                    documents=backup_data["documents"],
                    embeddings=backup_data["embeddings"],
                    metadatas=backup_data["metadatas"],
                    ids=backup_data["ids"]
                )
                self.collections["wikipedia"] = collection
                print(f"Successfully restored {collection_name} from Firebase backup")
            else:
                print(f"Incomplete or missing backup data for {collection_name}")
        except Exception as e:
            print(f"Error restoring from backup: {str(e)}")

    def query_place(self, place_name: str, limit: int = 3, similarity_threshold: float = 0.5) -> dict:
        """Query collections and penalize irrelevant results based on similarity score and return empty if no relevant results."""
        results = {}

        for source, collection in self.collections.items():
            try:
                # Perform vector search (if using embeddings)
                query_result = collection.query(
                    query_texts=[place_name],
                    n_results=limit
                )

                if query_result and query_result['documents']:
                    documents = query_result['documents']
                    scores = query_result['distances']  # Assuming the API returns distances (cosine similarity)
                    metadatas = query_result['metadatas']  # Assuming metadata is available

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
                        # Optionally, you can re-rank the filtered documents based on their final scores
                        # Sorting by score (higher score means more relevant)
                        sorted_docs = sorted(zip(filtered_documents, filtered_scores), key=lambda x: x[1], reverse=True)
                        results[source] = [doc for doc, _ in sorted_docs[:limit]]
                    else:
                        results[source] = []  # No relevant documents passed the threshold
                else:
                    # Fallback to simple text matching if vector search fails
                    backup_data = self.firebase_backup.load_collection(f"{source}_collection")
                    if backup_data and backup_data.get('documents'):
                        # Simple text search with relevance scoring based on string matching
                        matched_docs = [
                            doc for doc in backup_data["documents"]
                            if place_name.lower() in doc.lower()
                        ]
                        if matched_docs:
                            results[source] = matched_docs[:limit]
                        else:
                            results[source] = []  # No documents found, return empty list
                    else:
                        results[source] = []  # No backup data, return empty list
            except Exception as e:
                print(f"Error querying {source}: {str(e)}")
                results[source] = []  # Return empty result in case of error

        # If no relevant documents are found across all sources, return empty result
        if all(len(res) == 0 for res in results.values()):
            return {}

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