import asyncio
import websockets
import json
import time
from typing import Dict, Set, Any, List

# Stores active connections
connected_clients: Set = set()

# Stores active calls with format:
# {
#   'call_id': {
#     'caller': WebSocket connection,
#     'offer': SDP offer,
#     'answerer': WebSocket connection (optional),
#     'answer': SDP answer (optional),
#     'timestamp': time when call was created,
#     'caller_candidates': [ICE candidates from caller],
#     'answerer_candidates': [ICE candidates from answerer]
#   }
# }
active_calls: Dict[str, Dict[str, Any]] = {}

# Assign unique client IDs
client_counter = 0
client_ids: Dict = {}

# Expiry time for calls (in seconds)
CALL_EXPIRY_TIME = 60

async def clean_expired_calls() -> None:
    """Remove expired calls that haven't been answered"""
    current_time = time.time()
    expired_call_ids = []
    
    for call_id, call_data in active_calls.items():
        # Check if call is expired and not answered yet
        if (current_time - call_data['timestamp'] > CALL_EXPIRY_TIME and
                'answerer' not in call_data):
            expired_call_ids.append(call_id)
    
    # Remove expired calls
    for call_id in expired_call_ids:
        print(f"Call {call_id} expired, removing from active calls")
        await broadcast_call_ended(call_id)
        active_calls.pop(call_id, None)

async def broadcast_call_ended(call_id: str) -> None:
    """Broadcast to all clients that a call has ended"""
    if call_id in active_calls:
        message = {
            'type': 'call_ended',
            'call_id': call_id
        }
        
        # Send to caller if still connected
        caller = active_calls[call_id].get('caller')
        if caller in connected_clients:
            try:
                await caller.send(json.dumps(message))
            except Exception as e:
                print(f"Error sending call ended to caller: {e}")
        
        # Send to answerer if exists and still connected
        answerer = active_calls[call_id].get('answerer')
        if answerer and answerer in connected_clients:
            try:
                await answerer.send(json.dumps(message))
            except Exception as e:
                print(f"Error sending call ended to answerer: {e}")

async def handle_call_offer(websocket, data: Dict[str, Any]) -> None:
    """Handle incoming call offer"""
    call_id = data['call_id']
    offer = data['offer']
    
    # Store call information with empty candidates lists
    active_calls[call_id] = {
        'caller': websocket,
        'offer': offer,
        'timestamp': time.time(),
        'caller_candidates': [],
        'answerer_candidates': []
    }
    
    # Broadcast call to all other connected clients
    broadcast_message = {
        'type': 'new_call',
        'call_id': call_id,
        'offer': offer
    }
    
    for client in connected_clients:
        if client != websocket:  # Don't send to caller
            try:
                await client.send(json.dumps(broadcast_message))
            except Exception as e:
                print(f"Error broadcasting call offer: {e}")

async def handle_call_answer(websocket, data: Dict[str, Any]) -> None:
    """Handle incoming call answer"""
    call_id = data['call_id']
    answer = data['answer']
    
    # Check if call exists
    if call_id not in active_calls:
        print(f"Answer for non-existent call {call_id}")
        return
    
    # Check if call already answered
    if 'answerer' in active_calls[call_id]:
        print(f"Call {call_id} already answered")
        return
    
    # Store answerer information
    active_calls[call_id]['answerer'] = websocket
    active_calls[call_id]['answer'] = answer
    
    # Send answer to caller
    caller = active_calls[call_id]['caller']
    if caller in connected_clients:
        answer_message = {
            'type': 'call_answered',
            'call_id': call_id,
            'answer': answer
        }
        try:
            await caller.send(json.dumps(answer_message))
        except Exception as e:
            print(f"Error sending answer to caller: {e}")
    
    # Send stored ICE candidates from caller to answerer
    await send_stored_candidates(call_id, 'caller_candidates', websocket)
    
    # Notify other clients that call has been taken
    taken_message = {
        'type': 'call_taken',
        'call_id': call_id
    }
    
    for client in connected_clients:
        if client != caller and client != websocket:
            try:
                await client.send(json.dumps(taken_message))
            except Exception as e:
                print(f"Error notifying call taken: {e}")

async def send_stored_candidates(call_id: str, 
                                candidates_key: str, 
                                recipient) -> None:
    """Send stored ICE candidates to a recipient"""
    if call_id in active_calls and candidates_key in active_calls[call_id]:
        stored_candidates = active_calls[call_id][candidates_key]
        
        for candidate in stored_candidates:
            ice_message = {
                'type': 'ice_candidate',
                'call_id': call_id,
                'candidate': candidate
            }
            try:
                await recipient.send(json.dumps(ice_message))
            except Exception as e:
                print(f"Error sending stored ICE candidate: {e}")

async def handle_ice_candidate(websocket, data: Dict[str, Any]) -> None:
    """Handle ICE candidate and forward to the appropriate peer"""
    call_id = data['call_id']
    candidate = data['candidate']
    
    if call_id not in active_calls:
        print(f"ICE candidate for non-existent call {call_id}")
        return
    
    call_data = active_calls[call_id]
    
    # Store the candidate in the appropriate list
    if websocket == call_data['caller']:
        call_data['caller_candidates'].append(candidate)
        
        # If there's an answerer, forward the candidate
        recipient = call_data.get('answerer')
        if recipient and recipient in connected_clients:
            ice_message = {
                'type': 'ice_candidate',
                'call_id': call_id,
                'candidate': candidate
            }
            try:
                await recipient.send(json.dumps(ice_message))
            except Exception as e:
                print(f"Error forwarding caller ICE candidate: {e}")
    
    elif 'answerer' in call_data and websocket == call_data['answerer']:
        call_data['answerer_candidates'].append(candidate)
        
        # Forward to caller if connected
        recipient = call_data['caller']
        if recipient in connected_clients:
            ice_message = {
                'type': 'ice_candidate',
                'call_id': call_id,
                'candidate': candidate
            }
            try:
                await recipient.send(json.dumps(ice_message))
            except Exception as e:
                print(f"Error forwarding answerer ICE candidate: {e}")

async def handle_end_call(websocket, data: Dict[str, Any]) -> None:
    """Handle request to end a call"""
    call_id = data['call_id']
    
    if call_id not in active_calls:
        print(f"End request for non-existent call {call_id}")
        return
    
    await broadcast_call_ended(call_id)
    active_calls.pop(call_id, None)

async def send_active_calls(websocket) -> None:
    """Send all active unanswered calls to a newly connected client"""
    current_time = time.time()
    
    for call_id, call_data in active_calls.items():
        # Only send unanswered calls that are not expired
        if ('answerer' not in call_data and 
                current_time - call_data['timestamp'] <= CALL_EXPIRY_TIME):
            call_message = {
                'type': 'new_call',
                'call_id': call_id,
                'offer': call_data['offer']
            }
            try:
                await websocket.send(json.dumps(call_message))
            except Exception as e:
                print(f"Error sending active call: {e}")

async def websocket_handler(websocket) -> None:
    """Handle WebSocket connections"""
    global client_counter
    
    # Assign a unique client ID
    client_id = str(client_counter)
    client_counter += 1
    client_ids[websocket] = client_id
    
    # Add to connected clients
    connected_clients.add(websocket)
    print(f"Client connected. Total clients: {len(connected_clients)}")
    
    # Send client ID
    try:
        await websocket.send(json.dumps({'client_id': client_id}))
    except Exception as e:
        print(f"Error sending client ID: {e}")
    
    # Send active calls
    await send_active_calls(websocket)
    
    try:
        async for message in websocket:
            # Clean expired calls periodically
            asyncio.create_task(clean_expired_calls())
            
            try:
                data = json.loads(message)
                
                # Handle different types of messages
                if 'offer' in data and 'call_id' in data:
                    await handle_call_offer(websocket, data)
                elif 'answer' in data and 'call_id' in data:
                    await handle_call_answer(websocket, data)
                elif 'candidate' in data and 'call_id' in data:
                    await handle_ice_candidate(websocket, data)
                elif 'type' in data and data['type'] == 'end_call' and 'call_id' in data:
                    await handle_end_call(websocket, data)
                else:
                    print(f"Unknown message format: {data}")
            except json.JSONDecodeError:
                print(f"Invalid JSON received: {message}")
    except websockets.exceptions.ConnectionClosed:
        print("Connection closed")
    finally:
        # Clean up when client disconnects
        if websocket in client_ids:
            client_id = client_ids[websocket]
            del client_ids[websocket]
        
        connected_clients.remove(websocket)
        print(f"Client disconnected. Total clients: {len(connected_clients)}")
        
        # End calls where this client was involved
        calls_to_remove = []
        for call_id, call_data in active_calls.items():
            if call_data['caller'] == websocket or call_data.get('answerer') == websocket:
                calls_to_remove.append(call_id)
                await broadcast_call_ended(call_id)
        
        for call_id in calls_to_remove:
            active_calls.pop(call_id, None)

async def main():
    server_host = '0.0.0.0'  # Listen on all available interfaces
    server_port = 50001
    
    print(f"Starting signaling server on {server_host}:{server_port}")
    
    # Updated server implementation without 'path' parameter
    async with websockets.serve(websocket_handler, server_host, server_port):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())