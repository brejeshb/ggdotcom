from flask import Flask, request, jsonify
from firebase_admin import credentials, firestore, initialize_app
from datetime import datetime
from flask_cors import CORS
from openai import OpenAI  # Correct import
import uuid
import os
import json

app = Flask(__name__)
CORS(app)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

@app.route('/')
def home():
    return "Tour Guide API is running!"


@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        
        if not data or 'prompt' not in data:
            return jsonify({'error': 'No prompt provided'}), 400

        # Get the prompt from the request
        prompt = data['prompt']
        
        # Optional parameters with defaults
        model = data.get('model', 'gpt-3.5-turbo')
        max_tokens = data.get('max_tokens', 150)
        temperature = data.get('temperature', 0.7)

        # Generate response using OpenAI
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=temperature
        )

        # Extract the response text
        response_text = response.choices[0].message.content

        # Create response object
        response_data = {
            'id': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat(),
            'prompt': prompt,
            'response': response_text
        }

        return jsonify(response_data)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Optional: Add a route to generate tour guide specific responses
@app.route('/tour-guide', methods=['POST'])
def tour_guide():
    try:
        data = request.get_json()
        
        if not data or 'location' not in data:
            return jsonify({'error': 'No location provided'}), 400

        location = data['location']
        interests = data.get('interests', [])
        duration = data.get('duration', '1 day')

        # Create a structured prompt for the tour guide response
        prompt = f"""Act as a knowledgeable local tour guide for {location}. 
        Create a personalized itinerary for {duration}"""
        
        if interests:
            prompt += f" focusing on: {', '.join(interests)}"

        # Generate response using OpenAI
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.7
        )

        response_text = response.choices[0].message.content

        # Create response object
        response_data = {
            'id': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat(),
            'location': location,
            'interests': interests,
            'duration': duration,
            'itinerary': response_text
        }

        return jsonify(response_data)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run()