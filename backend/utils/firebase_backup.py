
import json
import tempfile
from typing import Dict, Optional, List
import firebase_admin
from firebase_admin import credentials, storage
import chromadb
import sys
import os
from firebase_init import initialize_firebase
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
# from backend.firebase_init import initialize_firebase
from config import get_chroma_settings


class FirebaseBackup:
    def __init__(self, bucket_name: str):
        # Use already initialized Firebase app or initialize it if not done yet
        try:
            self.bucket = storage.bucket(bucket_name)
            print(f"Connected to Firebase bucket: {bucket_name}")
        except ValueError:
            firebase_app = initialize_firebase(bucket_name)
            self.bucket = storage.bucket(bucket_name)
            print(f"Connected to Firebase bucket: {bucket_name}")
        
        settings = get_chroma_settings()
        self.chroma_client = chromadb.HttpClient(
            host=settings["chroma_host"],
            port=settings["chroma_port"],
            ssl=settings["chroma_ssl"],
            headers={"X-Api-Key": settings["chroma_api_key"]} if settings["chroma_api_key"] else None
        )

    def list_firebase_collections(self) -> List[str]:
        """List all ChromaDB collections in Firebase Storage"""
        try:
            base_path = "ggdotcom/chroma_db/"
            blobs = list(self.bucket.list_blobs(prefix=base_path))
            
            # Get unique collection IDs by looking at the directory structure
            collections = set()
            for blob in blobs:
                # Split path and get the collection ID directory
                parts = blob.name.split('/')
                if len(parts) > 3 and parts[2] != "chroma.sqlite3":
                    collections.add(parts[2])
            
            return list(collections)
        except Exception as e:
            print(f"Error listing collections: {str(e)}")
            return []

    def load_collection(self, collection_id: str) -> Optional[Dict]:
        """Load collection data from Firebase Storage using collection ID"""
        base_path = f"ggdotcom/chroma_db/{collection_id}"
        result = {}

        try:
            print(f"\nAttempting to load collection ID: {collection_id}")
            blobs = list(self.bucket.list_blobs(prefix=base_path))

            if not blobs:
                print(f"No files found for collection ID: {collection_id}")
                return None

            print("\nFound files in collection:")
            for blob in blobs:
                print(f"- {blob.name}")

            # Load binary files
            binary_files = ['data_level0.bin', 'header.bin', 'length.bin', 'link_lists.bin']
            for file_name in binary_files:
                blob = next((b for b in blobs if b.name.endswith(file_name)), None)
                if blob:
                    with tempfile.NamedTemporaryFile(mode='r+b', delete=False) as temp_file:
                        blob.download_to_filename(temp_file.name)
                        with open(temp_file.name, 'rb') as f:
                            key = file_name.split('.')[0]
                            result[key] = f.read()
                            print(f"Loaded binary file: {file_name}")
                        os.unlink(temp_file.name)

            if all(k in result for k in ['data_level0', 'header', 'length']):
                print("Successfully loaded all required binary files")
                return result
            else:
                print("Missing some required files")
                return None

        except Exception as e:
            print(f"Error loading collection: {str(e)}")
            return None

    def get_collection_details(self, collection_id: str) -> Dict:
        """Get details about a collection from ChromaDB"""
        try:
            collection = self.chroma_client.get_collection(collection_id)
            result = collection.get()
            
            return {
                'id': collection_id,
                'count': len(result['ids']) if result['ids'] else 0,
                'documents': result if result['ids'] else None
            }
        except Exception as e:
            print(f"Error getting collection details: {str(e)}")
            return {'id': collection_id, 'error': str(e)}

    def view_collection(self, collection_id: str) -> None:
        """View all documents in a collection by ID"""
        try:
            details = self.get_collection_details(collection_id)
            
            if 'error' in details:
                print(f"\nError accessing collection: {details['error']}")
                return
                
            if not details['documents']:
                print(f"\nNo documents found in collection ID: {collection_id}")
                return
                
            print(f"\n=== Documents in Collection '{collection_id}' ===")
            print(f"Total documents: {details['count']}")
            
            for i, doc_id in enumerate(details['documents']['ids']):
                print(f"\nDocument {i + 1}/{details['count']}")
                print("=" * 50)
                print(f"ID: {doc_id}")
                
                if details['documents']['metadatas']:
                    metadata = details['documents']['metadatas'][i]
                    print("\nMetadata:")
                    print("-" * 20)
                    for key, value in metadata.items():
                        print(f"{key}: {value}")
                
                if details['documents']['documents']:
                    print("\nDocument Preview:")
                    print("-" * 20)
                    text = details['documents']['documents'][i]
                    print(f"{text[:200]}...")
                print("=" * 50)
                
        except Exception as e:
            print(f"\nError viewing collection: {str(e)}")