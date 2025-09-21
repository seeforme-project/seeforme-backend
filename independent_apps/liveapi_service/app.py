import asyncio
import base64
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types
import os


prompt_path = os.path.join(os.path.dirname(__file__), "prompt.txt")
with open(prompt_path, "r", encoding="utf-8") as f:
    prompt_text = f.read().strip()

app = FastAPI()

GOOGLE_API_KEY = "GEMINI_API_KEY"

if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY is not set")

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Client connected.")
    await websocket.send_json({"type": "instantiating_connection"})

    client = genai.Client(api_key=GOOGLE_API_KEY)
    model = "gemini-2.0-flash-live-001" # "gemini-2.5-flash-preview-native-audio-dialog"

    # Define function declarations for function calling
    navigation_request = {
        "name": "navigation_request",
        "description": "Handle navigation requests from the user",
        "parameters": {
            "type": "object",
            "properties": {
                "destination": {
                    "type": "string",
                    "description": "The destination or location the user wants to navigate to"
                },
                "navigation_type": {
                    "type": "string",
                    "description": "Type of navigation (e.g., 'directions', 'location_info', 'route_planning')",
                    "enum": ["directions", "location_info", "route_planning"]
                }
            },
            "required": ["destination"]
        }
    }

    tools = [{"function_declarations": [navigation_request]}]

    config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection={
                "prefix_padding_ms": 300,
                "silence_duration_ms": 500,
            }
        ),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Zephyr"
                )
            ),
            language_code="en-US"
        ),
        system_instruction=types.Content(
            parts=[types.Part(text=prompt_text)]
        ),
        generation_config=types.GenerationConfig(
            temperature=0.5,
            top_k=64,
            top_p=0.95,
        ),
        tools=tools,
    )

    try:
        async with client.aio.live.connect(model=model, config=config) as session:
            await websocket.send_json({"type": "successfully_connected"})

            async def send_to_gemini():
                try:
                    while True:
                        message_event = await websocket.receive()

                        if message_event['type'] == 'websocket.receive':
                            # Binary audio (raw stream)
                            if 'bytes' in message_event:
                                binary_message = message_event['bytes']
                                print(f"[AUDIO RECEIVED] Length: {len(binary_message)} bytes")
                                await session.send_realtime_input(
                                    audio=types.Blob(
                                        data=binary_message,
                                        mime_type="audio/pcm;rate=16000",
                                    )
                                )

                            # JSON text (image, control events)
                            elif 'text' in message_event:
                                text_message = message_event['text']
                                try:
                                    json_data = json.loads(text_message)
                    
                                    if json_data.get("type") == "image_input":
                                        base64_image = json_data["image_data"]
                                        image_bytes = base64.b64decode(base64_image)
                                        print(f"[VIDEO FRAME RECEIVED] Length: {len(image_bytes)} bytes, Type: {json_data.get('mime_type', 'image/jpeg')}")
                                        await session.send_realtime_input(
                                            **{
                                                "video": types.Blob(
                                                    data=image_bytes,
                                                    mime_type=json_data.get("mime_type", "image/jpeg"), # Sending as JPEG MIME type
                                                )
                                            }
                                        )
                                        print(f"[VIDEO FRAME SENT] Length: {len(image_bytes)} bytes, Type: {json_data.get('mime_type', 'image/jpeg')}")


                                    elif json_data.get("type") == "audio_stream_end":
                                        print("[CONTROL] Frontend signaled audio stream end.")
                                        await session.send_realtime_input(audio_stream_end=True)
                                    else:
                                        print(f"[WARNING] Unhandled JSON message type: {json_data.get('type')}")
                                except Exception as e:
                                    print(f"Error processing text message: {e}")

                            else:
                                print(f"[WARNING] Event with no text or bytes: {message_event}")

                        elif message_event['type'] == 'websocket.disconnect':
                            print("Client disconnected (send stream).")
                            return
                        else:
                            print(f"[WARNING] Unhandled event type: {message_event['type']}")

                except WebSocketDisconnect:
                    print("Client disconnected (send stream via exception).")
                    return
                except Exception as e:
                    print(f"Error in send stream: {e}")

            async def receive_gemini_responses():
                try:
                    while True:
                        async for response in session.receive():
                            if getattr(response.server_content, "interrupted", False):
                                print("[GEMINI] Interrupted!")
                                await websocket.send_json({"type": "interrupted"})
                            
                            if getattr(response, "data", None):
                                await websocket.send_bytes(response.data)
                            
                            if getattr(response.server_content, "turn_complete", False):
                                print("[GEMINI] Turn complete!")
                                await websocket.send_json({"type": "turn_complete"})
                            
                            # Handle tool calls (function calling)
                            await handle_tool_calls(response, session)
                                
                except WebSocketDisconnect:
                    print("Client disconnected (Gemini response stream).")
                    return
                except Exception as e:
                    print("Error in Gemini response stream:", e)

            await asyncio.gather(
                send_to_gemini(),
                receive_gemini_responses(),
            )
    except Exception as e:
        print(f"Error during Gemini session setup: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Failed to connect to Gemini: {str(e)}"
            })
        except Exception:
            pass
        await websocket.close()





#

#

#

#

#

#

#

#

#

#

#

#


# Stub function for navigation requests
def handle_navigation_request(destination: str, navigation_type: str = "directions"):
    """Stub function for handling navigation requests"""
    print(f"Navigation request called - Destination: {destination}, Type: {navigation_type}")
    return {"status": "success", "message": f"Navigation request processed for {destination}"}



#

#

#

#

#

#


async def handle_tool_calls(response, session):
    if hasattr(response, 'tool_call') and response.tool_call:
        print("[GEMINI] Tool call received!")
        function_responses = []
        
        for fc in response.tool_call.function_calls:
            print(f"[FUNCTION CALL] {fc.name} called with args: {fc.args}")
            
            if fc.name == "navigation_request":
                # Extract arguments
                destination = fc.args.get("destination", "")
                navigation_type = fc.args.get("navigation_type", "directions")
                
                # Call our stub function
                result = handle_navigation_request(destination, navigation_type)
                
                # Create function response
                function_response = types.FunctionResponse(
                    id=fc.id,
                    name=fc.name,
                    response=result
                )
            else:
                # Handle unknown function calls
                function_response = types.FunctionResponse(
                    id=fc.id,
                    name=fc.name,
                    response={"error": f"Unknown function: {fc.name}"}
                )
            
            function_responses.append(function_response)
        
        # Send tool responses back to Gemini
        await session.send_tool_response(function_responses=function_responses)
        print("[GEMINI] Tool responses sent!")