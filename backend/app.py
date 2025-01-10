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

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()

        if not data or 'location' not in data:
            return jsonify({'error': 'No location provided'}), 400

        # Receive coordinates
        location = data.get('location', "")
        print(f"Location Received: {location}")

        try:
            # Parse location string into lat, lng
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
            address = location  # Fallback to coordinates if there's an error

        # Add address to prompt
        prompt = f"""You are a Singapore Tour Guide, please provide details regarding the nearest point of interest in the nearby surrounding with the coordinates of
                {address} where the user would be able to visually see.
                Start by saying, You see [Point of interest]. Do not mention anything about coordinates.
                Include only one specific landmark and describe in detail regarding history or context."""
        
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
            # create msg data for firestore
            message_data = {
                'timestamp': datetime.now(),
                'message_Id': "",
                'chatText': response_text,
                'image': "",
                'location': location,
                'userCheck': "",
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

# Configure for gunicorn
if __name__ == "__main__":
    # If running directly
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
else:
    # For gunicorn
    application = app
