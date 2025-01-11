import chromadb
import sys
import os
from firebase_backup import FirebaseBackup
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from backend.config import get_chroma_settings, get_firebase_backup

class ChromaDBManager:
    def __init__(self):
        settings = get_chroma_settings()
        self.chroma_client = chromadb.HttpClient(
            host=settings["chroma_host"],
            port=settings["chroma_port"],
            ssl=settings["chroma_ssl"],
            headers={"X-Api-Key": settings["chroma_api_key"]} if settings["chroma_api_key"] else None
        )
        firebase_settings = get_firebase_backup()
        self.firebase_backup = FirebaseBackup(firebase_settings["bucket_name"])

    def verify_backup(self, collection_name: str) -> bool:
        """
        Verify if a collection exists both in ChromaDB and Firebase backup
        """
        try:
            # Check ChromaDB
            chroma_collection = self.chroma_client.get_collection(collection_name)
            chroma_data = chroma_collection.get()
            
            # Check Firebase backup
            backup_data = self.firebase_backup.load_collection(collection_name)
            
            if not backup_data:
                print(f"No backup found for collection '{collection_name}'")
                return False
                
            # Compare document counts
            chroma_count = len(chroma_data['ids']) if chroma_data['ids'] else 0
            backup_count = len(backup_data['ids']) if backup_data['ids'] else 0
            
            if chroma_count != backup_count:
                print(f"Document count mismatch: ChromaDB has {chroma_count}, Firebase has {backup_count}")
                return False
                
            print(f"Successfully verified backup for '{collection_name}'")
            print(f"Total documents: {chroma_count}")
            return True
            
        except ValueError:
            print(f"Collection '{collection_name}' not found in ChromaDB")
            return False
        except Exception as e:
            print(f"Error verifying backup: {str(e)}")
            return False

    def list_collections(self):
        """List all collections in the ChromaDB instance."""
        collections = self.chroma_client.list_collections()
        print(f"Found collections: {collections}")
        if collections:
            print("\n=== ChromaDB Collections ===")
            for collection_name in collections:
                print(f"Collection Name: {collection_name}")
                # Also verify backup status
                self.verify_backup(collection_name)
        else:
            print("\nNo collections found in ChromaDB.")

    def view_collection(self, collection_name: str) -> None:
        """View all documents in a ChromaDB collection by name."""
        try:
            collection = self.chroma_client.get_collection(collection_name)
            result = collection.get()
            
            if not result or not result['ids']:
                print(f"\nNo documents found in collection '{collection_name}'.")
                return
                
            print(f"\n=== Documents in Collection '{collection_name}' ===")
            
            for i in range(len(result['ids'])):
                print(f"\nDocument {i + 1}/{len(result['ids'])}")
                print("=" * 50)
                print(f"ID: {result['ids'][i]}")
                
                metadata = result['metadatas'][i]
                print("\nMetadata:")
                print("-" * 20)
                for key, value in metadata.items():
                    print(f"{key}: {value}")
                
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
        """Delete a ChromaDB collection by name."""
        collections = self.chroma_client.list_collections()
        collection_exists = collection_name in collections
        
        if collection_exists:
            self.chroma_client.delete_collection(collection_name)
            print(f"\nCollection '{collection_name}' has been deleted.")
        else:
            print(f"\nCollection '{collection_name}' not found.")

    def inspect_firebase_backup(self, collection_name: str) -> None:
        """
        View all documents in a Firebase backup collection and optionally restore to ChromaDB
        """
        try:
            print(f"\n=== Inspecting Firebase Backup for Collection '{collection_name}' ===")
            
            # Load collection from Firebase backup
            backup_data = self.firebase_backup.load_collection(collection_name)
            
            if not backup_data:
                print(f"\nNo backup found for collection '{collection_name}'")
                return
                
            print("\nBackup Data Overview:")
            print("=" * 50)
            
            # Display information about binary files
            for key, data in backup_data.items():
                print(f"\n{key}:")
                print(f"Size: {len(data)} bytes")
                print(f"Type: Binary data")
                
            print("\nBinary Files Structure:")
            print("=" * 50)
            print("data_level0.bin - Contains the main data")
            print("header.bin - Contains collection metadata")
            print("length.bin - Contains length information")
            print("link_lists.bin - Contains linking information")
            
            # Ask if user wants to restore the collection to ChromaDB
            restore = input("\nWould you like to restore this collection to ChromaDB? (y/n): ")
            if restore.lower() == 'y':
                success = self.firebase_backup.restore_collection(collection_name)
                if success:
                    print(f"\nSuccessfully initiated restoration of collection '{collection_name}' to ChromaDB")
                    print("Note: Binary data loaded but processing needs to be implemented")
                else:
                    print(f"\nFailed to restore collection '{collection_name}' to ChromaDB")
                    
        except Exception as e:
            print(f"\nError inspecting collection from Firebase backup: {str(e)}")
if __name__ == "__main__":
    # Initialize ChromaDB Manager
    manager = ChromaDBManager()

    # List collections in ChromaDB
    manager.list_collections()

    # View documents in a specific collection in Firebase
    # collection_to_view = input("\nEnter the name of the collection you want to view: ")
    # manager.inspect_firebase_backup(collection_to_view)

    # Optionally, delete a collection by name (if desired)
    # collection_to_delete = input("\nEnter the name of the collection you want to delete: ")
    # manager.delete_collection(collection_to_delete)

    # Initialize the backup manager
    backup_manager = FirebaseBackup("ggdotcom-254aa.firebasestorage.app")

    # List all collections in Firebase
    collections = backup_manager.list_firebase_collections()
    print("Available collections:", collections)

    # View a specific collection
    # collection_id = "bb6f9d1a-7823-40fb-82d5-3f4fab3b4eba"
    # backup_manager.view_collection("wikipedia_collection")
