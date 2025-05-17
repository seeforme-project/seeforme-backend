from django.urls import path
from . import views

urlpatterns = [
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('token/refresh/', views.token_refresh_view, name='token_refresh'),
    path('logout/', views.logout_view, name='logout'),


    path('register-notification-token/', views.register_token, name='register-token'),
    path('send-push-notification/', views.send_push_notification, name='send-push-notification'),





    # For video calling signaling
    path('broadcast-offer', views.broadcast_offer, name='broadcast_offer'),
    path('check-for-incoming-calls', views.check_for_incoming_calls, name='check_for_incoming_calls'),
    path('send-answer', views.send_answer, name='send_answer'),
    path('check-answer/<str:call_id>', views.check_answer, name='check_answer'),
    path('send-ice-candidate', views.send_ice_candidate, name='send_ice_candidate'),
    path('check-ice-candidates/<str:call_id>/<str:user_id>', views.check_ice_candidates, name='check_ice_candidates'),
    path('end-call', views.end_call, name='end_call'),
]