import firebase_admin
from firebase_admin import credentials

def initialize_firebase(bucket_name: str):
    try:
        # Attempt to get the default app
        app = firebase_admin.get_app()
    except ValueError:
        # If not initialized, initialize the app with the credentials and bucket
        cred = credentials.Certificate("./ggdotcom-254aa-firebase-adminsdk-1nske-fd0d2cac2a.json")
        app = firebase_admin.initialize_app(cred, {
            'storageBucket': bucket_name
        })
    return app
