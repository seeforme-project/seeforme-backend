from django.shortcuts import render
from django.contrib.auth import authenticate
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .utils.jwt_utils import *
import json
from .models import *


import firebase_admin
from firebase_admin import credentials, messaging

# import base dir
import os
from pathlib import Path


# In prod (hf spaces) as a secret in env:
serviceAccountKeyJSON = os.getenv('firebase_seeforme_service_account') # secret in hf space env
if serviceAccountKeyJSON:
    # convert it to a dict
    serviceAccountKey = json.loads(serviceAccountKeyJSON)
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    # As a file, as in local
    serviceAccountKey = os.path.join(BASE_DIR, 'secrets/seeforme-app-firebase-adminsdk-fbsvc-27bc3eafa6.json')


# Path to your Firebase service account key JSON file
cred = credentials.Certificate(serviceAccountKey)
firebase_admin.initialize_app(cred)


# Send notifs - API, to send push notifications to a single device
from firebase_admin import messaging

def send_push_notification(token, title, body, data=None):
    """
    Sends a push notification to a single device using FCM.
    
    Args:
        token (str): FCM device token.
        title (str): Notification title.
        body (str): Notification body.
        data (dict, optional): Additional data payload.
    """
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            token=token,
            data=data if data else {}
        )
        response = messaging.send(message)
        print(f"Notification sent successfully: {response}")
        return True
    except Exception as e:
        print(f"Error sending notification: {e}")
        return False

# New function to send call request to a specific user
def send_call_request(caller_user, callee_user):
    """
    Sends a call request notification to a specific user.
    
    Args:
        caller_user (User): The user initiating the call.
        callee_user (User): The user receiving the call.
    """
    if not callee_user.device_fcm_token:
        return False, "Recipient user has no registered device"
    
    call_data = {
        "call_type": "video",
        "call_action": "incoming",
        "caller_id": str(caller_user.id),
        "caller_name": caller_user.username,
        "caller_email": caller_user.email,
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    success = send_push_notification(
        token=callee_user.device_fcm_token,
        title="Incoming Video Call",
        body=f"Incoming call from {caller_user.username}",
        data=call_data
    )
    
    return success, "Call request sent successfully" if success else "Failed to send call request"

# New function to broadcast a call to multiple users
def broadcast_call_to_users(caller_user, recipient_user_ids=None):
    """
    Broadcasts a call request to multiple users.
    
    Args:
        caller_user (User): The user initiating the call.
        recipient_user_ids (list, optional): List of user IDs to send the call to.
                                            If None, will broadcast to all users except caller.
    
    Returns:
        tuple: (success_count, failed_count, error_messages)
    """
    if recipient_user_ids:
        recipients = User.objects.filter(id__in=recipient_user_ids)
    else:
        # Broadcast to all users except the caller
        recipients = User.objects.exclude(id=caller_user.id).filter(device_fcm_token__isnull=False)
    
    success_count = 0
    failed_count = 0
    error_messages = []
    
    for recipient in recipients:
        success, message = send_call_request(caller_user, recipient)
        if success:
            success_count += 1
        else:
            failed_count += 1
            error_messages.append(f"Failed to send to {recipient.username}: {message}")
    
    return success_count, failed_count, error_messages

# Register token sent for each user, by the frontend
@csrf_exempt
@token_required
def register_fcm_token(request):
    if request.method == 'POST':
        token = request.headers.get('token')
        username = decode_jwt_token(token)
        user = User.objects.get(username=username)
        if user:
            device_fcm_token = request.POST.get('device_fcm_token')
            user.device_fcm_token = device_fcm_token
            user.save()

            # If token registered successfully, send a test notification
            send_push_notification(
                token=device_fcm_token,
                title="HEHE FCM Token Registered",
                body="You will now receive notifications from Maju Trackmate"
            )
            return JsonResponse({"message": "FCM token registered successfully"}, status=200)
        return JsonResponse({"error": "User not found"}, status=404)
    return JsonResponse({"error": "Invalid request"}, status=400)

# New endpoint for initiating a call request
@csrf_exempt
@token_required
def initiate_call_request(request):
    """
    API endpoint for a user to initiate a call request to another user or broadcast to multiple users.
    """
    if request.method == 'POST':
        try:
            # Get caller user
            token = request.headers.get('token')
            username = decode_jwt_token(token)
            caller_user = User.objects.get(username=username)
            
            data = json.loads(request.body)
            recipient_id = data.get('recipient_id')
            is_broadcast = data.get('is_broadcast', False)
            
            if is_broadcast:
                # Optional list of recipient IDs for targeted broadcast
                recipient_ids = data.get('recipient_ids', None)
                success_count, failed_count, errors = broadcast_call_to_users(caller_user, recipient_ids)
                
                return JsonResponse({
                    "success": success_count > 0,
                    "message": f"Call broadcast to {success_count} users with {failed_count} failures",
                    "success_count": success_count,
                    "failed_count": failed_count,
                    "errors": errors
                }, status=200 if success_count > 0 else 400)
            else:
                # Single user call
                if not recipient_id:
                    return JsonResponse({"error": "Recipient ID is required"}, status=400)
                
                try:
                    recipient_user = User.objects.get(id=recipient_id)
                    success, message = send_call_request(caller_user, recipient_user)
                    
                    return JsonResponse({
                        "success": success,
                        "message": message
                    }, status=200 if success else 400)
                except User.DoesNotExist:
                    return JsonResponse({"error": "Recipient user not found"}, status=404)
                
        except User.DoesNotExist:
            return JsonResponse({"error": "Caller user not found"}, status=404)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    
    return JsonResponse({"error": "Invalid request method"}, status=405)