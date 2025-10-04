import datetime
import jwt
import mongoengine
import os
from flask import Flask, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from dotenv import load_dotenv

# --- NEW: Import Firebase Admin SDK ---
import firebase_admin
from firebase_admin import credentials, firestore, messaging

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
MONGO_URI = os.environ.get("MONGODB_URI")
JWT_SECRET = os.environ.get("JWT_SECRET")

if not MONGO_URI or not JWT_SECRET:
    raise RuntimeError("MONGODB_URI and JWT_SECRET must be set in the environment or a .env file.")

JWT_ALGORITHM = 'HS256'
JWT_ACCESS_EXPIRATION = datetime.timedelta(minutes=30)
JWT_REFRESH_EXPIRATION = datetime.timedelta(days=1)

# --- App Initialization and DB Connection ---
app = Flask(__name__)
app.config["SECRET_KEY"] = JWT_SECRET

# Connect to MongoDB
try:
    mongoengine.connect(host=MONGO_URI)
    print("Successfully connected to MongoDB.")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")

# --- NEW: Initialize Firebase Admin SDK (Production-Ready) ---
import base64
import json

try:
    # Check for the production environment variable first
    encoded_service_account = os.environ.get("FIREBASE_SERVICE_ACCOUNT_BASE64")

    if encoded_service_account:
        print("Found Firebase credentials in environment variable. Initializing for production.")
        # Decode the Base64 string
        decoded_service_account = base64.b64decode(encoded_service_account).decode('utf-8')
        # Parse the JSON string into a dictionary
        service_account_info = json.loads(decoded_service_account)
        # Initialize the app with the credentials dictionary
        cred = credentials.Certificate(service_account_info)
        firebase_admin.initialize_app(cred)
        print("Successfully initialized Firebase Admin SDK from environment variable.")
    else:
        # Fallback to local file for development
        print("Firebase environment variable not found. Looking for local serviceAccountKey.json file.")
        cred_path = os.path.join(os.path.dirname(__file__), 'serviceAccountKey.json')
        if os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            print("Successfully initialized Firebase Admin SDK from local file.")
        else:
            print("WARNING: 'serviceAccountKey.json' not found. Firebase features will be unavailable.")
            
except Exception as e:
    print(f"FATAL: Error initializing Firebase Admin SDK: {e}")


# --- Models (defined with core mongoengine) ---
class User(mongoengine.Document):
    name = mongoengine.StringField(required=True, max_length=255)
    email = mongoengine.EmailField(required=True, unique=True)
    password = mongoengine.StringField(required=True)
    is_active = mongoengine.BooleanField(default=True)
    is_staff = mongoengine.BooleanField(default=False)
    account_type = mongoengine.StringField(max_length=50, choices=['volunteer', 'blind', 'admin'], default='volunteer')

    meta = {'collection': 'users'}

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def to_json(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'email': self.email,
            'account_type': self.account_type,
        }

# --- Helper Functions and Decorators ---
def generate_tokens(user_id):
    access_payload = {
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + JWT_ACCESS_EXPIRATION,
        'type': 'access'
    }
    refresh_payload = {
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + JWT_REFRESH_EXPIRATION,
        'type': 'refresh'
    }
    access_token = jwt.encode(access_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    refresh_token = jwt.encode(refresh_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return access_token, refresh_token

def jwt_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authentication token is required'}), 401
        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            if payload.get('type') != 'access':
                return jsonify({'error': 'Invalid token type'}), 401
            user_id = payload.get('user_id')
            user = User.objects.get(id=user_id)
            request.user = user
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except (jwt.InvalidTokenError, mongoengine.errors.DoesNotExist):
            return jsonify({'error': 'Authentication failed'}), 401
        return f(*args, **kwargs)
    return decorated

# --- API Routes ---
@app.route('/signup', methods=['POST'])
def signup_view():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    account_type = data.get('account_type')
    if not all([name, email, password, account_type]):
        return jsonify({'error': 'All fields are required'}), 400
    if User.objects(email=email).first():
        return jsonify({'error': 'User with this email already exists'}), 400
    user = User(name=name, email=email, account_type=account_type)
    user.set_password(password)
    user.save()
    access_token, refresh_token = generate_tokens(str(user.id))
    return jsonify({
        'user': user.to_json(),
        'access_token': access_token,
        'refresh_token': refresh_token
    }), 201

@app.route('/login', methods=['POST'])
def login_view():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400
    email = data.get('email')
    password = data.get('password')
    if not all([email, password]):
        return jsonify({'error': 'Email and password are required'}), 400
    user = User.objects(email=email).first()
    if user and user.check_password(password):
        access_token, refresh_token = generate_tokens(str(user.id))
        return jsonify({
            'user': user.to_json(),
            'access_token': access_token,
            'refresh_token': refresh_token
        })
    else:
        return jsonify({'error': 'Invalid credentials'}), 401




# --- NEW: Endpoint to replace Cloud Function (Simplified) ---
@app.route('/call-volunteer', methods=['POST'])
def call_volunteer_view():
    """
    Finds ALL available volunteers and sends them a push notification with the meeting ID.
    """
    if not firebase_admin._apps:
        return jsonify({'error': 'Firebase is not configured on the server.'}), 500

    data = request.get_json()
    meeting_id = data.get('meetingId')
    if not meeting_id:
        return jsonify({'error': 'meetingId is required'}), 400

    try:
        db = firestore.client()
        
        # The query is now simpler: just find all documents where isAvailable is true.
        # We don't need to order or limit anymore.
        volunteers_ref = db.collection('volunteers').where(filter=firestore.FieldFilter('isAvailable', '==', True)).stream()
        
        # Collect all the valid device tokens
        fcm_tokens = []
        for volunteer_doc in volunteers_ref:
            volunteer_data = volunteer_doc.to_dict()
            token = volunteer_data.get('fcmToken')
            if token: # Only add if the token exists and is not empty
                fcm_tokens.append(token)

        # Check if we found any volunteers at all
        if not fcm_tokens:
            print("No available volunteers with FCM tokens were found.")
            return jsonify({'error': 'No volunteers are available right now. Please try again later.'}), 404

        print(f"Found {len(fcm_tokens)} available volunteers. Sending notifications.")

        # Construct a single message to send to multiple devices
        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title='Incoming Call for Assistance!',
                body='Someone needs your help. Tap to join the call.',
            ),
            data={
                'meetingId': meeting_id,
                'click_action': 'FLUTTER_NOTIFICATION_CLICK', 
            },
            tokens=fcm_tokens, # The list of all tokens
        )

        # Use send_multicast to efficiently notify everyone at once
        response = messaging.send_multicast(message)
        print(f'Successfully sent messages to {response.success_count} devices.')
        if response.failure_count > 0:
            print(f'Failed to send messages to {response.failure_count} devices.')

        return jsonify({'message': f'Successfully notified {response.success_count} volunteers.'}), 200

    except Exception as e:
        print(f"An error occurred inside call_volunteer_view: {type(e).__name__}: {e}")
        return jsonify({'error': f'An internal server error occurred while contacting volunteers.: {type(e).__name__}: {e}'}), 500



@app.route('/token/refresh', methods=['POST'])
def token_refresh_view():
    data = request.get_json()
    refresh_token = data.get('refresh_token')
    if not refresh_token:
        return jsonify({'error': 'Refresh token is required'}), 400
    try:
        payload = jwt.decode(refresh_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get('type') != 'refresh':
            return jsonify({'error': 'Invalid token type'}), 400
        user_id = payload.get('user_id')
        access_token, new_refresh_token = generate_tokens(user_id)
        return jsonify({
            'access_token': access_token,
            'refresh_token': new_refresh_token
        })
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Invalid token'}), 401

@app.route('/logout', methods=['POST'])
@jwt_required
def logout_view():
    return jsonify({'message': 'Successfully logged out'})

@app.route('/profile', methods=['GET'])
@jwt_required
def profile_view():
    user = request.user
    return jsonify({
        'message': 'Successfully accessed protected route.',
        'user': user.to_json()
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=7860, threaded=True)