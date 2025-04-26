from django.urls import path
from . import views

urlpatterns = [
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('token/refresh/', views.token_refresh_view, name='token_refresh'),
    path('logout/', views.logout_view, name='logout'),


    path('register-notification-token/', views.register_token, name='register-token'),
    path('send-push-notification/', views.send_push_notification, name='send-push-notification'),
]