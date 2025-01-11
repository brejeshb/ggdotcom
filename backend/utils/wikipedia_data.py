import os
import time
from typing import List, Dict, Optional
import wikipediaapi
import googlemaps
from dotenv import load_dotenv
import chromadb
from chromadb.utils import embedding_functions
from datetime import datetime
import urllib.parse
import logging
from difflib import SequenceMatcher

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from backend.config import get_chroma_settings
import re

logging.basicConfig(level=logging.INFO)
load_dotenv()

def clean_name(name: str) -> str:
    """Clean name by removing special characters and standardizing format"""
    name = name.split('|')[0].strip()
    name = re.sub(r'[^\w\s-]', '', name)
    name = ' '.join(name.split())
    return name.lower()

def similar(a: str, b: str) -> float:
    """Calculate similarity ratio between two strings"""
    return SequenceMatcher(None, clean_name(a), clean_name(b)).ratio()


class WikipediaDataCollector:
    def __init__(self, attractions_array: dict):
        settings = get_chroma_settings()
        self.chroma_client = chromadb.HttpClient(
            host=settings["chroma_host"],
            port=settings["chroma_port"],
            ssl=settings["chroma_ssl"],
            headers={"X-Api-Key": settings["chroma_api_key"]} if settings["chroma_api_key"] else None
        )
        self.embedding_function = embedding_functions.DefaultEmbeddingFunction()

        # Delete existing collections if they exist
        try:
            self.chroma_client.delete_collection("wikipedia_collection")
            self.chroma_client.delete_collection("singapore_attractions")
        except Exception:
            pass  # Collections might not exist, that's okay

        # Create collections
        try:
            self.wiki_collection = self.chroma_client.create_collection(
                name="wikipedia_collection",
                metadata={"description": "Wikipedia documents for tourist attractions"},
                embedding_function=self.embedding_function
            )
            
            self.attractions_collection = self.chroma_client.create_collection(
                name="singapore_attractions",
                metadata={"description": "Tourist attractions in Singapore"},
                embedding_function=self.embedding_function
            )
            logging.info("Successfully created ChromaDB collections")
        except Exception as e:
            logging.error(f"Error creating collections: {str(e)}")
            raise


        # Initialize other necessary components
        self.wiki = wikipediaapi.Wikipedia(
            language='en',
            extract_format=wikipediaapi.ExtractFormat.WIKI,
            user_agent='SingaporeTourGuideBot/1.0'
        )
        
        self.gmaps = googlemaps.Client(key=os.getenv("GOOGLE_API_KEY"))
        
        # Initialize tracking variables
        self.attractions_array = attractions_array
        self.success_count = 0
        self.failure_count = 0
        self.successful_documents = []
        self.unsuccessful_documents = []
    def get_places(self, latitude: float, longitude: float, radius: int = 1000) -> List[Dict]:
        """
        Get nearby tourist attractions using Google Maps Places API
        """
        places_result = self.gmaps.places_nearby(
            location=(latitude, longitude),
            radius=radius,
            type='tourist_attraction',
            language='en'
        )
        
        all_places = []
        if 'results' in places_result:
            all_places.extend(places_result['results'])
            
            while 'next_page_token' in places_result:
                time.sleep(2)
                places_result = self.gmaps.places_nearby(
                    location=(latitude, longitude),
                    page_token=places_result['next_page_token']
                )
                if 'results' in places_result:
                    all_places.extend(places_result['results'])
                    
        return all_places

    def find_attraction_in_array(self, attraction_name: str) -> tuple:
        """
        Find attraction in the predefined array using fuzzy matching
        """
        best_match = None
        best_category = None
        best_url = None
        highest_ratio = 0.8  # Minimum similarity threshold

        cleaned_attraction = clean_name(attraction_name)
        
        for category in ["One", "Two", "Three"]:
            for item in self.attractions_array[category]:
                similarity = similar(cleaned_attraction, item["name"])
                if similarity > highest_ratio:
                    highest_ratio = similarity
                    best_match = item["name"]
                    best_category = category
                    best_url = item["url"]
                
                # Also check if the attraction name is contained within the item name or vice versa
                if (cleaned_attraction in clean_name(item["name"]) or 
                    clean_name(item["name"]) in cleaned_attraction):
                    if similarity > 0.5:  # Lower threshold for contained matches
                        best_match = item["name"]
                        best_category = category
                        best_url = item["url"]
                        highest_ratio = similarity

        if best_match:
            print(f"Matched '{attraction_name}' to '{best_match}' with similarity {highest_ratio:.2f}")
            return best_category, best_url
        return None, None

    def get_wikipedia_content(self, url: str) -> Optional[Dict]:
        """
        Enhanced Wikipedia content retrieval with better error handling
        """
        if not url or url == "N/A":
            return None
            
        try:
            page_title = urllib.parse.unquote(url.split("/")[-1].replace("_", " "))
            page = self.wiki.page(page_title)
            
            if not page.exists():
                search_results = self.wiki.search(page_title)
                if search_results:
                    page = self.wiki.page(search_results[0])
                else:
                    return None
            
            if page.exists():
                # Extract most relevant sections
                content = {
                    "summary": page.summary,
                    "history": "",
                    "description": "",
                    "url": url
                }
                
                # Parse full text to find relevant sections
                sections = page.text.split('\n\n')
                for section in sections:
                    lower_section = section.lower()
                    if any(keyword in lower_section for keyword in ["history", "background", "established"]):
                        content["history"] += section + "\n"
                    elif any(keyword in lower_section for keyword in ["description", "architecture", "features"]):
                        content["description"] += section + "\n"
                
                return content
                
        except Exception as e:
            logging.error(f"Error fetching Wikipedia content for {url}: {str(e)}")
        
        return None

    def store_in_chromadb(self, documents: List[Dict]) -> None:
        """
        Store only successfully processed Wikipedia documents in ChromaDB
        """
        # Filter for successful Wikipedia documents only
        wiki_docs = [doc for doc in documents if doc["metadata"].get("wikipedia_url") 
                    and doc["text"] != "No Wikipedia content available"]
        
        if not wiki_docs:
            logging.info("No successful Wikipedia documents to store")
            return
            
        try:
            # Prepare data for ChromaDB
            texts = [doc["text"] for doc in wiki_docs]
            metadatas = [doc["metadata"] for doc in wiki_docs]
            ids = [doc["metadata"]["place_id"] for doc in wiki_docs]
            
            # Store in Wikipedia collection
            self.wiki_collection.add(
                documents=texts,
                metadatas=metadatas,
                ids=ids
            )
            
            logging.info(f"Successfully stored {len(wiki_docs)} documents in wikipedia_collection")
            
            # Verify storage by querying
            results = self.wiki_collection.query(
                query_texts=["test query"],
                n_results=1
            )
            if results and len(results['ids']) > 0:
                logging.info("Storage verification successful")
            else:
                logging.warning("Storage verification failed - no results returned")
                
        except Exception as e:
            logging.error(f"Error storing documents in ChromaDB: {str(e)}")

    def create_document_structure(self, attraction: Dict, wiki_content: Optional[Dict]) -> Dict:
        """
        Create enhanced document structure with better content organization
        """
        if wiki_content:
            # Combine relevant content with proper structure
            relevant_text = (
                f"Summary:\n{wiki_content['summary']}\n\n"
                f"History:\n{wiki_content['history']}\n\n"
                f"Description:\n{wiki_content['description']}"
            ).strip()
        else:
            relevant_text = "No Wikipedia content available"

        return {
            "text": relevant_text,
            "metadata": {
                "place_id": attraction.get("place_id", ""),
                "name": attraction["name"],
                "category": "tourist_attraction",
                "source": "wikipedia" if wiki_content else "google",
                "fact_type": "historical" if wiki_content else "basic",
                "last_verified": datetime.now().strftime("%Y-%m-%d"),
                "wikipedia_url": wiki_content["url"] if wiki_content else "",
                "has_wiki_content": bool(wiki_content)
            }
        }

    def process_attractions(self, latitude: float, longitude: float) -> List[Dict]:
        """
        Process attractions with improved error handling and logging
        """
        try:
            attractions = self.get_places(latitude, longitude)
            logging.info(f"Found {len(attractions)} attractions")
            
            documents = []
            for attraction in attractions:
                try:
                    logging.info(f"Processing: {attraction['name']}")
                    category, url = self.find_attraction_in_array(attraction["name"])
                    
                    if category and (category in ["One", "Two"]):
                        wiki_content = self.get_wikipedia_content(url)
                        if wiki_content:
                            self.success_count += 1
                            self.successful_documents.append({"name": attraction["name"], "url": url})
                            logging.info(f"Successfully retrieved Wikipedia content from {url}")
                        else:
                            self.failure_count += 1
                            self.unsuccessful_documents.append(attraction["name"])
                            logging.warning(f"Failed to retrieve Wikipedia content from {url}")
                    else:
                        self.failure_count += 1
                        self.unsuccessful_documents.append(attraction["name"])
                        wiki_content = None
                        
                    document = self.create_document_structure(attraction, wiki_content)
                    documents.append(document)
                    
                except Exception as e:
                    logging.error(f"Error processing attraction {attraction['name']}: {str(e)}")
                    continue
            
            self.store_in_chromadb(documents)
            self.print_results()
            return documents
            
        except Exception as e:
            logging.error(f"Error in process_attractions: {str(e)}")
            return []

    def print_results(self):
        """
        Print processing results
        """
        print("\n=== Processing Results ===")
        print(f"Total attractions processed: {self.success_count + self.failure_count}")
        print(f"Successfully processed: {self.success_count}")
        print(f"Failed to process: {self.failure_count}")
        
        print("\n--- Successful Processing ---")
        for item in self.successful_documents:
            print(f"✓ {item['name']}: {item['url']}")
        
        print("\n--- Failed Processing ---")
        for name in self.unsuccessful_documents:
            print(f"✗ {name}")
        
        print("\n========================")



# Using an array to manually update the incorrect urls in
# One is successful and correct
# Two is correct context but not specific to the building
# Three is dont exist in Wikipedia, or not exactly the same thing

if __name__ == "__main__":
    attractions_array = {
        "One": [
            {"name": "Cavenagh Bridge", "url": "https://en.wikipedia.org/wiki/Cavenagh_Bridge"},
            {"name": "Lau Pa Sat", "url": "https://en.wikipedia.org/wiki/Lau_Pa_Sat"},
            {"name": "Sri Mariamman Temple", "url": "https://en.wikipedia.org/wiki/Sri_Mariamman_Temple,_Singapore"},
            {"name": "Masjid Omar Kampong Melaka", "url": "https://en.wikipedia.org/wiki/Masjid_Omar_Kampong_Melaka"},
            {"name": "Tan Si Chong Su Temple", "url": "https://en.wikipedia.org/wiki/Tan_Si_Chong_Su"},


            {"name": "Yu Huang Gong - Temple of the Heavenly Jade Emperor", "url": "https://en.wikipedia.org/wiki/Temple_of_the_Heavenly_Jade_Emperor"},
        
            {"name": "Bollywood Beats", "url": "https://en.wikipedia.org/wiki/Bollywood_Beats"},
            {"name": "Elgin Bridge", "url": "https://en.wikipedia.org/wiki/Elgin_Bridge_(Singapore)"},
            {"name": "Pearl's Hill City Park", "url": "https://en.wikipedia.org/wiki/Pearl%27s_Hill_City_Park"},
            {"name": "Sri Layan Sithi Vinayagar Temple", "url": "https://en.wikipedia.org/wiki/Sri_Layan_Sithi_Vinayagar_Temple"},
            {"name": "Boat Quay", "url": "https://en.wikipedia.org/wiki/Boat_Quay"},
            {"name": "Masjid Al-Abrar", "url": "https://en.wikipedia.org/wiki/Masjid_Al-Abrar"},
            {"name": "STPI Creative Workshop and Gallery", "url": "https://en.wikipedia.org/wiki/STPI_-_Creative_Workshop_%26_Gallery"},


            {"name": "Temple Street @ Chinatown", "url": "https://en.wikipedia.org/wiki/Temple_Street,_Singapore"},



            {"name": "Chinatown", "url": "https://en.wikipedia.org/wiki/Chinatown,_Singapore"},



            {"name": "Buddha Tooth Relic Temple", "url": "https://en.wikipedia.org/wiki/Buddha_Tooth_Relic_Temple_and_Museum"},



            {"name": "Club Street", "url": "https://en.wikipedia.org/wiki/Club_Street"},
            {"name": "Maxwell Food Centre", "url": "https://en.wikipedia.org/wiki/Maxwell_Food_Centre"},
            {"name": "Jinrikisha Station", "url": "https://en.wikipedia.org/wiki/Jinrikisha_Station"},

            {"name": "Nagore Dargah", "url": "https://en.wikipedia.org/wiki/Nagore_Durgha,_Singapore"},
            {"name": "Hong Lim Park", "url": "https://en.wikipedia.org/wiki/Hong_Lim_Park"},


            {"name": "Telok Ayer Green", "url": "https://en.wikipedia.org/wiki/Telok_Ayer_Street"},

            {"name": "Read Bridge", "url": "https://en.wikipedia.org/wiki/Read_Bridge"},
            {"name": "Clarke Quay", "url": "https://en.wikipedia.org/wiki/Clarke_Quay"},

        ],
        "Two": [


            {"name": "Chinatown Singapore", "url": "https://en.wikipedia.org/wiki/Chinatown,_Singapore"},
            {"name": "Singapore River Cruise", "url": "https://en.wikipedia.org/wiki/Singapore_River"},


            {"name": "Peking Opera Ping She", "url": "https://en.wikipedia.org/wiki/Peking_opera"},
            {"name": "Ann Siang Hill Park", "url": "https://en.wikipedia.org/wiki/Ann_Siang_Hill"},
            {"name": "Siang Cho Keong Temple", "url": "https://en.wikipedia.org/wiki/Amoy_Street,_Singapore"},
            {"name": "Amoy Street Conservation Shophouses", "url": "https://en.wikipedia.org/wiki/Amoy_Street,_Singapore"},
            {"name": "Hong Lim Market & Food Centre", "url": "https://en.wikipedia.org/wiki/Hawker_centre"},
        ],
        "Three": [

            #Murals
            {"name": "Mural: Lanterns", "url": "https://en.wikipedia.org/wiki/Historic_Filipinotown,_Los_Angeles"},
            {"name": "Chinatown Street Arts", "url": "https://en.wikipedia.org/wiki/Chinatown,_Philadelphia"},
            {"name": "Mural - Bruce Lee", "url": "https://en.wikipedia.org/wiki/Mural"},
            {"name": "Singaporean Radio memories", "url": "https://en.wikipedia.org/wiki/Chinese_Singaporeans"},
            {"name": "Conan's Wall Art", "url": "https://en.wikipedia.org/wiki/Conan_O%27Brien"},
            {"name": "Kreta Ayer link wall painting", "url": "https://en.wikipedia.org/wiki/Chinese_New_Year"},
            {"name": "Moo Moo the Cat Portrait", "url": "https://en.wikipedia.org/wiki/Alley_Oop"},
            {"name": "Mohamed Ali Lane Murals", "url": "https://en.wikipedia.org/wiki/Music_of_Egypt"},
            {"name": "Chinatown Market - Wall Mural Art by Yip Yew Chong", "url": "https://en.wikipedia.org/wiki/Index_of_Singapore-related_articles"},
            {"name": "Mural: Chinatown home", "url": "https://en.wikipedia.org/wiki/Chinatown,_Vancouver"},
            {"name": "Mural - Singapore Hawker Heritage", "url": "https://en.wikipedia.org/wiki/Culture_of_Singapore"},
            {"name": "Mid-Autumn Festival by Yip Yew Chong", "url": "N/A"},
            {"name": "Paper Mask & Puppet Seller by Yip Yew Chong", "url": "N/A"},
            {"name": "牛车水街市 (Chinatown Market)", "url": "N/A"},
            {"name": "Mural Samsui Lady with Cigarette", "url": "N/A"},
            {"name": "Peking Street Murals", "url": "N/A"},
            {"name": "Art Installation at Eu Tong Sen Street & Hill Street / Upper Cross Street", "url": "N/A"},
            {"name": "Sunday Flea Market", "url": "N/A"},
            {"name": "Yong Kee Food Supply Wall Mural", "url": "N/A"},
            {"name": "Cantonese Opera - Wall Mural by Yip Yew Chong", "url": "N/A"},

            #Businesses
            {"name": "Trally", "url": "https://en.wikipedia.org/wiki/Ph%C3%BA_Qu%E1%BB%91c"},
            {"name": "Oo La Lab @ Chinatown", "url": "https://en.wikipedia.org/wiki/Deaths_in_June_2024"},

            #others
            {"name": "VR WORLD Singapore", "url": "N/A"}, 
            {"name": "Open Space outside OG Chinatown", "url": "N/A"}, 
            {"name": "Old Wall @ Far East Square", "url": "https://en.wikipedia.org/wiki/The_Fullerton_Hotel_Singapore"},
            {"name": "Chinatown Heritage Centre", "url": "https://en.wikipedia.org/wiki/Chinatown,_Singapore"},
            {"name": "Singapore Musical Box Museum", "url": "https://en.wikipedia.org/wiki/List_of_museums_in_Singapore"},

            ## I cant read so I skipped this
            {"name": "牛车水广场", "url": "https://en.wikipedia.org/wiki/List_of_village-level_divisions_of_Hubei"}
            ]
    }

    
    collector = WikipediaDataCollector(attractions_array)
    CHINATOWN_LAT = 1.2836
    CHINATOWN_LNG = 103.8440
    documents = collector.process_attractions(CHINATOWN_LAT, CHINATOWN_LNG)
