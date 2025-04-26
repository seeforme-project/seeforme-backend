from django.urls import path
from . import firebase

urlpatterns = [
    # ... your existing URL patterns
    path('api/register-fcm-token/', firebase.register_fcm_token, name='register_fcm_token'),
    path('api/initiate-call/', firebase.initiate_call_request, name='initiate_call_request'),
]