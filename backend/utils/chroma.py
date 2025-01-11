import chromadb
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from backend.config import get_chroma_settings



class ChromaDBManager:
    def __init__(self):
        settings = get_chroma_settings()
        self.chroma_client = chromadb.HttpClient(
            host=settings["chroma_host"],
            port=settings["chroma_port"],
            ssl=settings["chroma_ssl"],
            headers={"X-Api-Key": settings["chroma_api_key"]} if settings["chroma_api_key"] else None
        )


    def list_collections(self):
        """
        List all collections in the ChromaDB instance.
        """
        collections = self.chroma_client.list_collections()  # This returns a list of collection names
        print(f"Found collections: {collections}")
        if collections:
            print("\n=== ChromaDB Collections ===")
            for collection_name in collections:
                print(f"Collection Name: {collection_name}")
        else:
            print("\nNo collections found in ChromaDB.")


    def view_collection(self, collection_name: str) -> None:
        """
        View all documents in a ChromaDB collection by name.
        
        Args:
            collection_name (str): Name of the collection to view ("wikipedia_collection" or "singapore_attractions")
        """
        try:
            # Get the collection
            collection = self.chroma_client.get_collection(collection_name)
            
            # Get all documents from the collection
            result = collection.get()
            
            if not result or not result['ids']:
                print(f"\nNo documents found in collection '{collection_name}'.")
                return
                
            print(f"\n=== Documents in Collection '{collection_name}' ===")
            
            # Iterate through all documents
            for i in range(len(result['ids'])):
                print(f"\nDocument {i + 1}/{len(result['ids'])}")
                print("=" * 50)
                
                # Print document ID
                print(f"ID: {result['ids'][i]}")
                
                # Print metadata
                metadata = result['metadatas'][i]
                print("\nMetadata:")
                print("-" * 20)
                for key, value in metadata.items():
                    print(f"{key}: {value}")
                
                # Print document text (first 200 characters)
                print("\nDocument Preview:")
                print("-" * 20)
                text = result['documents'][i]
                print(f"{text[:200]}...")
                
                print("=" * 50)
                
        except ValueError as e:
            print(f"\nError: Collection '{collection_name}' not found.")
        except Exception as e:
            print(f"\nError viewing collection: {str(e)}")



    def delete_collection(self, collection_name: str):
        """
        Delete a ChromaDB collection by name.
        """
        collections = self.chroma_client.list_collections()  # Updated to use self.chroma_client
        collection_exists = collection_name in collections  # Directly check if the collection name is in the list
        
        if collection_exists:
            self.chroma_client.delete_collection(collection_name)  # Updated to use self.chroma_client
            print(f"\nCollection '{collection_name}' has been deleted.")
        else:
            print(f"\nCollection '{collection_name}' not found.")

if __name__ == "__main__":
    # Initialize ChromaDB Manager
    manager = ChromaDBManager()

    # List collections in ChromaDB
    manager.list_collections()

    # View documents in a specific collection
    collection_to_view = input("\nEnter the name of the collection you want to view: ")
    manager.view_collection(collection_to_view)

    # Optionally, delete a collection by name (if desired)
    # collection_to_delete = input("\nEnter the name of the collection you want to delete: ")
    # manager.delete_collection(collection_to_delete)
