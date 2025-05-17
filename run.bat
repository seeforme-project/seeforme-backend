@echo off
echo Starting Django and WebSocket signaling server...

REM Start Django dev server
start "Django Server" cmd /k python manage.py runserver 0.0.0.0:8000

REM Start signaling server
start "Signaling Server" cmd /k python bundled_microservices/webrtc_signaling_server/a.py

echo Both servers started in separate terminals.
pause
