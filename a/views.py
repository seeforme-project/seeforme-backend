import json
import jwt
import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.conf import settings




User = get_user_model()




# Settings for JWT
JWT_SECRET = 'your-secret-key'  # Change this in production
JWT_ALGORITHM = 'HS256'
JWT_ACCESS_EXPIRATION = datetime.timedelta(minutes=30)
JWT_REFRESH_EXPIRATION = datetime.timedelta(days=1)







@csrf_exempt
def generate_tokens(user_id):
    """Generate access and refresh tokens for a user"""
    access_payload = {
        'user_id': user_id,
        'exp': datetime.datetime.now(datetime.timezone.utc) + JWT_ACCESS_EXPIRATION,
        'type': 'access'
    }
    
    refresh_payload = {
        'user_id': user_id,
        'exp': datetime.datetime.now(datetime.timezone.utc) + JWT_REFRESH_EXPIRATION,
        'type': 'refresh'
    }
    
    access_token = jwt.encode(access_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    refresh_token = jwt.encode(refresh_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    return access_token, refresh_token








@csrf_exempt
def signup_view(request):
    """Simple signup view"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name')
            email = data.get('email')
            password = data.get('password')

            account_type = data.get('account_type')

            
            
            # Basic validation
            if not all([name, email, password, account_type]):
                return JsonResponse({'error': 'All fields are required'}, status=400)
            
            # Check if user already exists
            if User.objects.filter(email=email).exists():
                return JsonResponse({'error': 'User with this email already exists'}, status=400)
            
            # Create user
            user = User.objects.create_user(email=email, name=name, password=password, account_type=account_type)
            
            # Generate tokens
            access_token, refresh_token = generate_tokens(user.id)
            
            return JsonResponse({
                'user': {
                    'id': user.id,
                    'name': user.name,
                    'email': user.email,
                    'account_type': user.account_type,
                },
                'access_token': access_token,
                'refresh_token': refresh_token
            }, status=201)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)








@csrf_exempt
def login_view(request):
    """Simple login view"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email')
            password = data.get('password')
            
            # Basic validation
            if not all([email, password]):
                return JsonResponse({'error': 'Email and password are required'}, status=400)
            
            # Authenticate user
            user = authenticate(request, username=email, password=password)
            
            if user is not None:
                login(request, user)
                
                # Generate tokens
                access_token, refresh_token = generate_tokens(user.id)
                
                return JsonResponse({
                    'user': {
                        'id': user.id,
                        'name': user.name,
                        'email': user.email,
                        'account_type': user.account_type,
                    },
                    'access_token': access_token,
                    'refresh_token': refresh_token
                })
            else:
                return JsonResponse({'error': 'Invalid credentials'}, status=401)
                
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)








@csrf_exempt
def token_refresh_view(request):
    """Simple token refresh view"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            refresh_token = data.get('refresh_token')
            
            if not refresh_token:
                return JsonResponse({'error': 'Refresh token is required'}, status=400)
            
            try:
                # Decode and validate the token
                payload = jwt.decode(refresh_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
                
                # Check if it's a refresh token
                if payload.get('type') != 'refresh':
                    return JsonResponse({'error': 'Invalid token type'}, status=400)
                
                user_id = payload.get('user_id')
                
                # Generate new tokens
                access_token, new_refresh_token = generate_tokens(user_id)
                
                return JsonResponse({
                    'access_token': access_token,
                    'refresh_token': new_refresh_token
                })
                
            except jwt.ExpiredSignatureError:
                return JsonResponse({'error': 'Token expired'}, status=401)
            except jwt.InvalidTokenError:
                return JsonResponse({'error': 'Invalid token'}, status=401)
                
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)









@csrf_exempt
def logout_view(request):
    """Simple logout view"""
    if request.method == 'POST':
        # In a real application, you would add the token to a blacklist
        # Here we'll just log the user out of the session
        logout(request)
        return JsonResponse({'message': 'Successfully logged out'})
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)












# A simple middleware function to check if a user is authenticated via JWT
def jwt_auth_middleware(get_response):
    def middleware(request):
        # Skip auth for login, signup, and token refresh endpoints
        if request.path in ['/api/login/', '/api/signup/', '/api/token/refresh/']:
            return get_response(request)
        
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            
            try:
                # Decode and validate the token
                payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
                
                # Check if it's an access token
                if payload.get('type') != 'access':
                    return JsonResponse({'error': 'Invalid token type'}, status=401)
                
                # Get the user
                user_id = payload.get('user_id')
                user = User.objects.get(pk=user_id)
                
                # Attach user to request
                request.user = user
                
            except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, User.DoesNotExist):
                return JsonResponse({'error': 'Authentication failed'}, status=401)
            
        return get_response(request)
    
    return middleware

































































































# For expo notification tokens
import requests

@csrf_exempt
def register_token(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    token = data.get('token')
    device_type = data.get('device_type')

    if not token:
        return JsonResponse({'error': 'Token is required'}, status=400)

    request.user.expo_notification_token = token
    request.user.device_type = device_type
    request.user.save()

    return JsonResponse({
        'message': 'Token registered successfully',
    }, status=200)



@csrf_exempt
def send_push_notification(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    user_id = data.get('user_id')
    title = data.get('title')
    message = data.get('message')

    if not user_id or not title or not message:
        return JsonResponse({
            'error': 'user_id, title and message are required'
        }, status=400)

    # Get user's expo token
    try:
        user = User.objects.get(pk=user_id)
        if not user.expo_notification_token:
            return JsonResponse({
                'error': f'No notification token found for user {user_id}'
            }, status=404)
        
        token = user.expo_notification_token
    except User.DoesNotExist:
        return JsonResponse({
            'error': f'User with id {user_id} not found'
        }, status=404)

    expo_push_api = 'https://exp.host/--/api/v2/push/send'

    # Create message payload for single user
    message_payload = {
        'to': token,
        'sound': 'default',
        'title': title,
        'body': message,
        'data': data.get('data', {})
    }

    try:
        response = requests.post(
            expo_push_api,
            data=json.dumps([message_payload]),  # Expo API expects an array
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            }
        )
        return JsonResponse(response.json(), status=response.status_code)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

















































































































































# For video calling signaling
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import time

# Simple in-memory storage
# In production, use Redis or another suitable storage solution
calls = {}
ice_candidates = {}

@csrf_exempt
@require_http_methods(["POST"])
def broadcast_offer(request):
    data = json.loads(request.body)
    call_id = data.get('callId')
    user_id = data.get('userId')
    offer = data.get('offer')
    
    # Store the broadcast call
    calls[call_id] = {
        'caller': user_id,
        'offer': offer,
        'status': 'pending',
        'created': int(time.time())
    }
    
    # Clean up old calls (older than 5 minutes)
    current_time = int(time.time())
    for cid in list(calls.keys()):
        if current_time - calls[cid].get('created', 0) > 300:  # 300 seconds = 5 minutes
            if calls[cid].get('status') == 'pending':
                del calls[cid]
    
    return JsonResponse({'success': True, 'callId': call_id})

@csrf_exempt
@require_http_methods(["GET"])
def check_for_incoming_calls(request):
    pending_calls = []
    
    # Find all pending calls
    for call_id, call_data in calls.items():
        if call_data.get('status') == 'pending':
            # Add call to the list
            pending_calls.append({
                'callId': call_id,
                'userId': call_data.get('caller'),
                'offer': call_data.get('offer')
            })
    
    return JsonResponse({'calls': pending_calls})

@csrf_exempt
@require_http_methods(["POST"])
def send_answer(request):
    data = json.loads(request.body)
    call_id = data.get('callId')
    user_id = data.get('userId')
    answer = data.get('answer')
    
    if call_id in calls:
        calls[call_id]['answer'] = answer
        calls[call_id]['answerer'] = user_id
        calls[call_id]['status'] = 'answered'
        return JsonResponse({'success': True})
    else:
        return JsonResponse({'success': False, 'error': 'Call not found'}, status=404)

@csrf_exempt
@require_http_methods(["GET"])
def check_answer(request, call_id):
    if call_id in calls and 'answer' in calls[call_id]:
        return JsonResponse({
            'success': True,
            'answer': calls[call_id]['answer'],
            'userId': calls[call_id]['answerer']
        })
    else:
        return JsonResponse({
            'success': False,
            'answer': None
        })

@csrf_exempt
@require_http_methods(["POST"])
def send_ice_candidate(request):
    data = json.loads(request.body)
    call_id = data.get('callId')
    user_id = data.get('userId')
    candidate = data.get('candidate')
    
    if call_id not in ice_candidates:
        ice_candidates[call_id] = {}
    
    if call_id not in calls:
        return JsonResponse({'success': False, 'error': 'Call not found'}, status=404)
    
    # Store candidates by user to send to the other party
    if calls[call_id]['caller'] == user_id and 'answerer' in calls[call_id]:
        other_user = calls[call_id]['answerer']
    elif 'answerer' in calls[call_id] and calls[call_id]['answerer'] == user_id:
        other_user = calls[call_id]['caller']
    else:
        return JsonResponse({'success': False, 'error': 'User not part of this call'}, status=400)
    
    if other_user not in ice_candidates[call_id]:
        ice_candidates[call_id][other_user] = []
    
    ice_candidates[call_id][other_user].append(candidate)
    
    return JsonResponse({'success': True})

@csrf_exempt
@require_http_methods(["GET"])
def check_ice_candidates(request, call_id, user_id):
    if (call_id in ice_candidates and 
        user_id in ice_candidates[call_id]):
        candidates = ice_candidates[call_id][user_id]
        # Clear the candidates after retrieving
        ice_candidates[call_id][user_id] = []
        return JsonResponse({
            'success': True,
            'candidates': candidates
        })
    else:
        return JsonResponse({
            'success': True,
            'candidates': []
        })

@csrf_exempt
@require_http_methods(["POST"])
def end_call(request):
    data = json.loads(request.body)
    call_id = data.get('callId')
    
    if call_id in calls:
        calls[call_id]['status'] = 'ended'
        
        # Clean up ice candidates
        if call_id in ice_candidates:
            del ice_candidates[call_id]
            
        return JsonResponse({'success': True})
    else:
        return JsonResponse({'success': False, 'error': 'Call not found'}, status=404)