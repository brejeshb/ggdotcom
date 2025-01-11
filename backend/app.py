from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
from firebase_admin import credentials, firestore, initialize_app
from datetime import datetime
import uuid
import os
import logging
import googlemaps
import firebase_admin
from firebase_admin import credentials
import requests
from typing import List, Dict
from utils.RAG import rag_manager


# Configure logging
logging.basicConfig(level=logging.ERROR)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Firestore initialization
cred = credentials.Certificate("./ggdotcom-254aa-firebase-adminsdk-1nske-fd0d2cac2a.json")
firebase_admin.initialize_app(cred)

# Firestore Client
db = firestore.client()

#Initialize Google Maps Key
gmap = googlemaps.Client(key=os.getenv("GOOGLE_API_KEY"))

# Initialize OpenAI API key
openai.api_key = os.getenv('OPENAI_API_KEY')

@app.route('/')
def home():
    return "Tour Guide API is running!"

def get_rag_information(place_name: str) -> Dict[str, List[str]]:
    """Fetch contextual information using local RAG manager"""
    try:
        print(f"Querying RAG for place: {place_name}")
        # Add collection check
        collections = rag_manager.collections
        print(f"Available collections: {collections}")
        
        # Try to get the collection and its count
        try:
            wiki_collection = rag_manager.client.get_collection("wikipedia_collection")
            count = wiki_collection.count()
            print(f"Wikipedia collection exists with {count} documents")
        except Exception as e:
            print(f"Error accessing wikipedia collection: {e}")
        
        results = rag_manager.query_place(place_name, limit=3)
        print(f"RAG query results: {results}")  # This will show what data was found
        return results
    except Exception as e:
        print(f"Error in RAG query: {str(e)}")
        return {}

def create_chat_messages(prompt: str, context: Dict[str, List[str]], is_image: bool = False, image_data: str = None) -> List[dict]:
    """Create chat messages with proper context integration"""
    messages = []
    
    # System message sets the role and basic context
    system_msg = {
        "role": "system",
        "content": "You are a knowledgeable Singapore Tour Guide. Use the provided context to give accurate, engaging responses, but maintain a natural conversational tone."
    }
    messages.append(system_msg)
    
    # Add context as a separate message if available
    if context:
        context_points = []
        for source, facts in context.items():
            for fact in facts:
                context_points.append(fact)
        if context_points:
            context_msg = {
                "role": "system",
                "content": "Here are some relevant facts about this location:\n" + "\n".join(context_points)
            }
            messages.append(context_msg)
    
    # Add the user's prompt with image if present
    if is_image and image_data:
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": prompt
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_data
                    }
                }
            ]
        })
    else:
        messages.append({
            "role": "user",
            "content": prompt
        })
    
    return messages


@app.route('/chat', methods=['POST'])

def chat():
    try:
        data = request.get_json()
        # Need factor cases with location, image (Base64)
        # if there is user input, add in to DB as well
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        location = data.get('location')
        image = data.get('image')
        text = data.get('text')
        print(f"Location: {location}")
        # print(f"Image: {image}")
        print(f"Text: {text}")

        # LOCATION WITH IMAGE WITH TEXT
        if location and text and image:
            try:
                #Get text data
                text_data = data.get('text')

                #Get location data
                location = data.get('location', "")
                print(f"Location Received: {location}")
                lat, lng = map(float, location.split(','))

                # Get address using Google Maps
                gmaps_result = gmap.reverse_geocode((lat, lng))

                if gmaps_result and len(gmaps_result) > 0:
                    address = gmaps_result[0]['formatted_address']
                else:
                    address = location  # Fallback to coordinates if geocoding fails
                
                print(f"Address: {address}")

            except Exception as e:
                print(f"Geocoding error: {str(e)}")
            
            image_data = data.get('image')

            try:
                # Check if it already has the prefix
                if image_data.startswith('data:image/jpeg;base64,'):
                    # Remove the prefix to clean the base64 string
                    base64_string = image_data.replace('data:image/jpeg;base64,', '')
                else:
                    base64_string = image_data
                    
                # Remove any whitespace or newlines
                base64_string = base64_string.strip().replace('\n', '').replace('\r', '')
                
                # Add the prefix back to image_data
                image_data = f"data:image/jpeg;base64,{base64_string}"
            except Exception as e:
                print(f"Error cleaning base64 image: {str(e)}")
                raise ValueError("Invalid base64 image data")

            context = get_rag_information(address)

            #Initalize prompt with text
            prompt = f"""You are a Singapore Tour Guide, please provide details regarding the text and photo that is given.
                You are also given the user's address of {address} to provide more context in regards to the users location.
                Do not mention the address in your answer.
                Answer what is given in the user's text and photo and describe in detail regarding history or context that is applicable.
                Here is the Users text: {text_data}"""

            print(prompt)
            # Create messages with context
            messages = create_chat_messages(prompt, context, is_image=True)
                
            try:
                # create USER msg data for firestore
                message_data = {
                    'timestamp': datetime.now(),
                    'message_Id': "",
                    'chatText': text_data,
                    'image': "",
                    'location': location,
                    'userCheck': "true",
                    'repeat': 0,
                }

                #Add to firestore
                db.collection("tour").document("yDLsVQhwoDF9ZHoG0Myk")\
                .collection('messages').add(message_data)
                
                print("Success: Added to Firestore")

            except Exception as e:
                print(f"Error: Failed to add to Firestore - {str(e)}")

            # Call OpenAI API
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                
                # CAN UNCOMMENT THIS BLOCK OF CODE and replace the messages right above to compare w and w/o RAG
                # [
                #     {
                #         "role": "user",
                #         "content": [
                #             {
                #                 "type": "text",
                #                 "text": prompt,
                #             }, 
                #             {
                #                 "type": "image_url",
                #                 "image_url": {
                #                     "url": image_data
                #                 }
                #             }
                #         ],
                #     },
                # ],
                max_tokens=500,
                temperature=0
            )

            # Extract response text
            response_text = response.choices[0].message.content

            print(f"Response: {response_text}")

            # Create response object
            response_data = {
                'id': uuid.uuid4().hex,
                'timestamp': datetime.now().isoformat(),
                'prompt': prompt,
                'response': response_text
            }

            try:
                # create REPLY msg data for firestore
                message_data = {
                    'timestamp': datetime.now(),
                    'message_Id': "",
                    'chatText': response_text,
                    'image': image_data,
                    'location': location,
                    'userCheck': "false",
                    'repeat': 0,
                }

                #Add to firestore
                db.collection("tour").document("yDLsVQhwoDF9ZHoG0Myk")\
                .collection('messages').add(message_data)
                
                print("Success: Added to Firestore")
            except Exception as e:
                print(f"Error: Failed to add to Firestore - {str(e)}")

            return jsonify(response_data)
        #END LOCATION WITH TEXT WITH IMAGE -------------------------------------------------------------

        #LOCATION WITH TEXT -------------------------------------------------------------
        elif location and text:
            try:
                #Get text data
                text_data = data.get('text')

                #Get location data
                location = data.get('location', "")
                print(f"Location Received: {location}")
                lat, lng = map(float, location.split(','))

                # Get address using Google Maps
                gmaps_result = gmap.reverse_geocode((lat, lng))

                if gmaps_result and len(gmaps_result) > 0:
                    address = gmaps_result[0]['formatted_address']
                else:
                    address = location  # Fallback to coordinates if geocoding fails
                
                print(f"Address: {address}")


            except Exception as e:
                print(f"Geocoding error: {str(e)}")

            context = get_rag_information(address)

            #Initalize prompt with text
            prompt = f"""You are a Singapore Tour Guide, please provide details regarding the text that is given.
                You are also given the user's address of {address} to provide more context in regards to the users location.
                Do not mention the address in your answer.
                Answer what is given in the user's text and describe in detail regarding history or context that is applicable.
                Here is the Users text: {text_data}"""

            print(prompt)
            messages = create_chat_messages(prompt, context)
                
            try:
                # create USER msg data for firestore
                message_data = {
                    'timestamp': datetime.now(),
                    'message_Id': "",
                    'chatText': text_data,
                    'image': "",
                    'location': location,
                    'userCheck': "true",
                    'repeat': 0,
                }

                #Add to firestore
                db.collection("tour").document("yDLsVQhwoDF9ZHoG0Myk")\
                .collection('messages').add(message_data)
                
                print("Success: Added to Firestore")

            except Exception as e:
                print(f"Error: Failed to add to Firestore - {str(e)}")

            # Call OpenAI API
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0
            )

            # Extract response text
            response_text = response.choices[0].message.content

            print(f"Response: {response_text}")

            # Create response object
            response_data = {
                'id': uuid.uuid4().hex,
                'timestamp': datetime.now().isoformat(),
                'prompt': prompt,
                'response': response_text
            }

            try:
                # create REPLY msg data for firestore
                message_data = {
                    'timestamp': datetime.now(),
                    'message_Id': "",
                    'chatText': response_text,
                    'image': "",
                    'location': location,
                    'userCheck': "false",
                    'repeat': 0,
                }

                #Add to firestore
                db.collection("tour").document("yDLsVQhwoDF9ZHoG0Myk")\
                .collection('messages').add(message_data)
                
                print("Success: Added to Firestore")
            except Exception as e:
                print(f"Error: Failed to add to Firestore - {str(e)}")

            return jsonify(response_data)
        #END LOCATION WITH TEXT -------------------------------------------------------------
        
        #LOCATION WITH IMAGE CHECK ----------------------------------------
        elif location and image:
            try:
                image_data = data.get('image')
                location = data.get('location', "")
                print(f"Location Received: {location}")
                lat, lng = map(float, location.split(','))

                # Get address using Google Maps
                gmaps_result = gmap.reverse_geocode((lat, lng))
                
                if gmaps_result and len(gmaps_result) > 0:
                    address = gmaps_result[0]['formatted_address']
                else:
                    address = location  # Fallback to coordinates if geocoding fails
                
                print(f"Address: {address}")

            except Exception as e:
                print(f"Geocoding error: {str(e)}")

            context = get_rag_information(address)
            #Initalize prompt with IMAGE
            prompt = f"""You are a Singapore Tour Guide, please provide details regarding the photo that is given.
                You are also given the user's address of {address} to provide more context in regards to where the photo is taken.
                Start by saying, You see [Point of interest]. Do not mention anything about the address in your answer.
                Include only what is given in the photo and describe in detail regarding history or context."""


            messages = create_chat_messages(prompt, context, is_image=True, image_data=image_data)

            try:
                # Check if it already has the prefix
                if image_data.startswith('data:image/jpeg;base64,'):
                    # Remove the prefix to clean the base64 string
                    base64_string = image_data.replace('data:image/jpeg;base64,', '')
                else:
                    base64_string = image_data
                    
                # Remove any whitespace or newlines
                base64_string = base64_string.strip().replace('\n', '').replace('\r', '')
                
                # Add the prefix back to image_data
                image_data = f"data:image/jpeg;base64,{base64_string}"
            except Exception as e:
                print(f"Error cleaning base64 image: {str(e)}")
                raise ValueError("Invalid base64 image data")

            # Call OpenAI API
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                
                # [
                #     {
                #         "role": "user",
                #         "content": [
                #             {
                #                 "type": "text",
                #                 "text": prompt,
                #             }, 
                #             {
                #                 "type": "image_url",
                #                 "image_url": {
                #                     "url": image_data
                #                 }
                #             }
                #         ],
                #     },
                # ],
                max_tokens=500,
                temperature=0
            )

            # Extract response text
            response_text = response.choices[0].message.content

            print(f"Response: {response_text}")
                
            # Create response object
            response_data = {
                'id': uuid.uuid4().hex,
                'timestamp': datetime.now().isoformat(),
                'prompt': prompt,
                'response': response_text
            }

            try:
                # create msg data for firestore
                message_data = {
                    'timestamp': datetime.now(),
                    'message_Id': "",
                    'chatText': response_text,
                    'image': image_data,
                    'location': location,
                    'userCheck': "false",
                    'repeat': 0,
                }

                #Add to firestore
                db.collection("tour").document("yDLsVQhwoDF9ZHoG0Myk")\
                .collection('messages').add(message_data)
                
                print("Success: Added to Firestore")
            except Exception as e:
                print(f"Error: Failed to add to Firestore - {str(e)}")

            return jsonify(response_data)
        #END LOCATION WITH IMAGE -------------------------------------------------------------

        #PURE LOCATION CHECK ----------------------------------------------------------------
        else:
            try:
                # Parse location string into lat, lng
                location = data.get('location', "")
                print(f"Location Received: {location}")
                lat, lng = map(float, location.split(','))
                
                # Get address using Google Maps
                gmaps_result = gmap.reverse_geocode((lat, lng))
                
                if gmaps_result and len(gmaps_result) > 0:
                    address = gmaps_result[0]['formatted_address']
                else:
                    address = location  # Fallback to coordinates if geocoding fails
                
                print(f"Address: {address}")

                # Get nearby tourist attractions
                places_result = gmap.places_nearby(
                    location=(lat, lng),
                    radius=500,  # 500m radius
                    type=['tourist_attraction', 'museum', 'art_gallery', 'park', 'shopping_mall', 
                        'hindu_temple', 'church', 'mosque', 'place_of_worship', 
                        'amusement_park', 'aquarium', 'zoo', 
                        'restaurant', 'cafe'],  # Specifically search for tourist attractions
                    language='en'  # Ensure English results
                        )

                if data.get('visitedPlaces'):
                    landmarks = data.get('visitedPlaces')
                else:
                    landmarks = []

                print("VISITED PLACES: " , landmarks)

                # Initialize place and number of repeats variable
                selected_place = None
                repeat = 0
                past_messages = []

                if places_result.get('results'):
                    for place in places_result['results']:
                        if (place['name'] in landmarks) :
                            continue
                        else :
                            landmarks.append(place['name'])
                            selected_place = place['name']
                            print("SELECTED PLACE: " , selected_place)
                            break
                            
                if not selected_place:
                    selected_place = address
                    #If place is repeated, start the firestore collection to retrieve past messages that was send out
                    most_recent_message = (
                                            db.collection('tour')
                                            .document("yDLsVQhwoDF9ZHoG0Myk")
                                            .collection('messages')
                                            .order_by('timestamp', direction='DESCENDING')
                                            .limit(1)
                                            .stream()
                                                )
                    for message in most_recent_message:
                        message_data = message.to_dict()
                        repeat = message_data.get('repeat')
                    #Retrieve that number of past messages that will be added to the prompt
                    repeated_messages = (
                                            db.collection('tour')
                                            .document("yDLsVQhwoDF9ZHoG0Myk")
                                            .collection('messages')
                                            .order_by('timestamp', direction='DESCENDING')
                                            .limit(repeat)
                                            .stream()
                                                )
                    chat_texts = []
                    for message in repeated_messages:
                        chat_text = message.to_dict().get('chatText', "")
                        if chat_text:
                            chat_texts.append(chat_text)
                    past_messages = " ".join(chat_texts)
                    repeat += 1


            except Exception as e:
                print(f"Geocoding error: {str(e)}")

            context = get_rag_information(selected_place)

            # Add address to prompt
            prompt = f"""You are a friendly Singapore Tour Guide giving a walking tour. If {selected_place} matches with {address}, this means you are in a residential or developing area.
            If both are the same you might have talked about this location already. Here are past messages you have send: [{past_messages}]. 
            If empty, means this is the first time you are talking about it.  
            If not empty, do not state the same thing again. Talk about something else about the area.

            For residential/developing areas:
            - Describe the most interesting aspects of the neighborhood or district you're in
            - Mention any nearby parks, nature areas, or community spaces
            - Include interesting facts about the area's development or future plans
            - Focus on what makes this area unique in Singapore

            For tourist landmarks:
            - Name and describe the specific landmark
            - Share its historical significance and background
            - Explain its cultural importance in Singapore
            - Describe unique architectural features
            - Include interesting facts that make it special

            Start with "You see [Point of interest/Area name]" and keep the tone friendly and conversational, as if speaking to tourists in person. Don't mention exact addresses or coordinates."""
            
            print("PROMPT", prompt)

            messages = create_chat_messages(prompt, context)

            # Call OpenAI API
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                
                # [
                #     {"role": "user", "content": prompt}
                # ],
                max_tokens=500,
                temperature=0.7
            )

            # Extract response text
            response_text = response.choices[0].message.content

            print(f"Response: {response_text}")

            # Create response object
            response_data = {
                'id': uuid.uuid4().hex,
                'timestamp': datetime.now().isoformat(),
                'prompt': prompt,
                'response': response_text,
                'visitedPlace' : selected_place
            }

            try:
                # create msg data for firestore
                message_data = {
                    'timestamp': datetime.now(),
                    'message_Id': "",
                    'chatText': response_text,
                    'image': "",
                    'location': location,
                    'userCheck': "false",
                    'repeat': repeat,
                }

                #Add to firestore
                db.collection("tour").document("yDLsVQhwoDF9ZHoG0Myk")\
                .collection('messages').add(message_data)
                
                print("Success: Added to Firestore")
            except Exception as e:
                print(f"Error: Failed to add to Firestore - {str(e)}")

            return jsonify(response_data)

    except Exception as e:
        logging.error("Error in /chat endpoint", exc_info=True)
        return jsonify({'error': str(e)}), 500
    #END PURE LOCATION CHECK ----------------------------------------------------------------

@app.route('/messages', methods = ['GET'])
def retrieve():
    try:    
        messages = db.collection('tour').document("yDLsVQhwoDF9ZHoG0Myk")\
                    .collection('messages')\
                    .order_by('timestamp', direction='DESCENDING' )\
                    .stream()
        
        message_list = []

        for msg in messages:
            msg_data = msg.to_dict()
            msg_data['id'] = msg.id
            # Convert timestamp to string for JSON serialization
            message_list.append(msg_data)
        
        return jsonify(message_list), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
        
    except Exception as e:
            logging.error("Error in /messages endpoint", exc_info=True)
            return jsonify({'error': str(e)}), 500


# For testing
@app.route('/test', methods = ['POST'])
def test():
    try:
        data = request.get_json()
        # Need factor cases with location, image (Base64)
        # if there is user input, add in to DB as well
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        text = data.get('text')
        print(f"Text: {text}")

        # TEXT
        if text:
            try:
                #Get text data
                text_data = data.get('text')

            except Exception as e:
                print(f"Text retrieval error: {str(e)}")
            

            #Initalize prompt with text
            prompt = f"""{text_data}"""



            print(prompt)
                
            # try:
            #     # create USER msg data for firestore
            #     message_data = {
            #         'timestamp': datetime.now(),
            #         'message_Id': "",
            #         'chatText': text_data,
            #         'image': "",
            #         'location': '',
            #         'userCheck': "true",
            #     }

            #     #Add to firestore
            #     db.collection("tour").document("yDLsVQhwoDF9ZHoG0Myk")\
            #     .collection('messages').add(message_data)
                
            #     print("Success: Added to Firestore")

            # except Exception as e:
            #     print(f"Error: Failed to add to Firestore - {str(e)}")

            # Call OpenAI API

            context = get_rag_information(text_data)


            messages = create_chat_messages(prompt, context)

            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages= messages,
                
                # [
                #     {
                #         "role": "user",
                #         "content": [
                #             {
                #                 "type": "text",
                #                 "text": prompt,
                #             }, 
                #         ],
                #     },
                # ],
                max_tokens=500,
                temperature=0
            )

            # Extract response text
            response_text = response.choices[0].message.content

            print(f"Response: {response_text}")

            # Create response object
            response_data = {
                'id': uuid.uuid4().hex,
                'timestamp': datetime.now().isoformat(),
                'prompt': prompt,
                'response': response_text
            }

            # try:
            #     # create REPLY msg data for firestore
            #     message_data = {
            #         'timestamp': datetime.now(),
            #         'message_Id': "",
            #         'chatText': response_text,
            #         'image': '',
            #         'location': location,
            #         'userCheck': "false",
            #     }

            #     #Add to firestore
            #     db.collection("tour").document("yDLsVQhwoDF9ZHoG0Myk")\
            #     .collection('messages').add(message_data)
                
            #     print("Success: Added to Firestore")
            # except Exception as e:
            #     print(f"Error: Failed to add to Firestore - {str(e)}")

            return jsonify(response_data)
        #END TEXT -------------------------------------------------------------

    except Exception as e:
        logging.error("Error in /test endpoint", exc_info=True)
        return jsonify({'error': str(e)}), 500


# Configure for gunicorn
if __name__ == "__main__":
    # If running directly
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
else:
    # For gunicorn
    application = app
