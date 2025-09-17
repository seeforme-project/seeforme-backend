import datetime
import jwt
import mongoengine
import os
from flask import Flask, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
# Get environment variables
# In production, these will be set directly as environment variables.
# In development, they will be loaded from the .env file.
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

# Connect to MongoDB directly using mongoengine
try:
    mongoengine.connect(host=MONGO_URI)
    print("Successfully connected to MongoDB.")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")

# --- Models (defined with core mongoengine) ---
class User(mongoengine.Document):
    name = mongoengine.StringField(required=True, max_length=255)
    email = mongoengine.EmailField(required=True, unique=True)
    password = mongoengine.StringField(required=True)
    is_active = mongoengine.BooleanField(default=True)
    is_staff = mongoengine.BooleanField(default=False)
    account_type = mongoengine.StringField(max_length=50, choices=['volunteer', 'blind', 'admin'], default='volunteer')

    # Meta data for the collection name
    meta = {
        'collection': 'users'
    }

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
    """Generate access and refresh tokens for a user"""
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
    """JWT Auth Decorator"""
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
            # Query using the core mongoengine API
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
    """Simple signup view"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    account_type = data.get('account_type')

    if not all([name, email, password, account_type]):
        return jsonify({'error': 'All fields are required'}), 400

    # Check if user exists using the core mongoengine API
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
    """Simple login view"""
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

@app.route('/token/refresh', methods=['POST'])
def token_refresh_view():
    """Simple token refresh view"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

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
    """Simple logout view"""
    # In a real-world app, you might add the token's jti to a blacklist.
    return jsonify({'message': 'Successfully logged out'})

# Protected route example
@app.route('/profile', methods=['GET'])
@jwt_required
def profile_view():
    """A protected route that returns the current user's info."""
    # The user object is attached to the request by the jwt_required decorator
    user = request.user
    return jsonify({
        'message': 'Successfully accessed protected route.',
        'user': user.to_json()
    })

# --- Main execution ---
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=7860, threaded=True)