from typing import List, Dict
import chromadb
from datetime import datetime, timedelta
from config import get_chroma_settings

class TourGuideRAG:
    def __init__(self):
        settings = get_chroma_settings()
        self.client = chromadb.HttpClient(
            host=settings["chroma_host"],
            port=settings["chroma_port"],
            ssl=settings["chroma_ssl"],
            headers={"X-Api-Key": settings["chroma_api_key"]} if settings["chroma_api_key"] else None
        )
        
        # Get existing collection instead of creating new one
        self.collection = self.client.get_collection(
            name="singapore_poi_facts"
        )
        # In-memory cache for recently mentioned facts
        self.fact_history = {}

    def _get_fresh_facts(self, place_id: str, name: str) -> List[str]:
        """
        Retrieve facts that haven't been recently mentioned
        """
        # Query vector store with place name and basic info
        results = self.collection.query(
            query_texts=[name],
            n_results=5,
            where={"place_id": place_id}
        )
        
        # Filter out recently used facts
        fresh_facts = []
        for fact in results['documents'][0]:
            fact_id = f"{place_id}_{hash(fact)}"
            if fact_id not in self.fact_history:
                fresh_facts.append(fact)
                # Mark fact as used
                self.fact_history[fact_id] = datetime.now()
                
        return fresh_facts

    def get_place_information(self, place_name: str) -> List[str]:
        """
        Retrieve information about a specific place
        """
        results = self.collection.query(
            query_texts=[place_name],
            n_results=3
        )
        
        if results and len(results['documents']) > 0:
            return results['documents'][0]
        return []