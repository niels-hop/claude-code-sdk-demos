from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json
from typing import Dict, Any
import asyncio

from session_manager import SessionManager
from claude_client import ClaudeClient
from custom_tools import create_email_tools_server
from config import PYTHON_BACKEND_HOST, PYTHON_BACKEND_PORT

app = FastAPI(title="Email Agent Python Backend")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
print("[Main] Creating email tools server...")
email_tools_server = create_email_tools_server()
print(f"[Main] Email tools server: {email_tools_server}")

session_manager = SessionManager()
claude_client = ClaudeClient(custom_tools_server=email_tools_server)

# Store active websocket connections
active_connections: Dict[WebSocket, str] = {}  # websocket -> session_id


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "email-agent-python-backend",
        "active_sessions": len(session_manager.get_active_sessions()),
        "active_connections": len(active_connections)
    }


@app.get("/health")
async def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "sessions": session_manager.get_active_sessions(),
        "connection_count": len(active_connections)
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for chat communication"""
    await websocket.accept()
    print(f"[WebSocket] Client connected")

    # Send welcome message
    await websocket.send_json({
        "type": "connected",
        "message": "Connected to Python backend",
        "availableSessions": session_manager.get_active_sessions()
    })

    current_session_id: str = None

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)

            print(f"[WebSocket] Received message type: {message.get('type')}")

            message_type = message.get("type")

            if message_type == "chat":
                # Handle chat message
                content = message.get("content", "")
                session_id = message.get("sessionId")
                new_conversation = message.get("newConversation", False)

                print(f"[WebSocket] Chat message - Session: {session_id}, New: {new_conversation}")
                print(f"[WebSocket] Content: {content[:100]}...")

                # Get or create session
                session = session_manager.get_or_create_session(session_id)
                current_session_id = session.id

                # Subscribe websocket to session
                session_manager.subscribe(session.id, websocket)
                active_connections[websocket] = session.id

                # End conversation if requested
                if new_conversation:
                    session_manager.end_conversation(session.id)

                # Echo user message to all subscribers
                await session_manager.broadcast_to_session(session.id, {
                    "type": "user_message",
                    "content": content,
                    "sessionId": session.id
                })

                # Process message with Claude (async task)
                asyncio.create_task(
                    process_claude_message(session.id, content, session.sdk_session_id)
                )

            elif message_type == "subscribe":
                # Subscribe to a session
                session_id = message.get("sessionId")
                if session_id in session_manager.sessions:
                    session_manager.subscribe(session_id, websocket)
                    current_session_id = session_id
                    active_connections[websocket] = session_id
                    await websocket.send_json({
                        "type": "subscribed",
                        "sessionId": session_id
                    })
                else:
                    await websocket.send_json({
                        "type": "error",
                        "error": "Session not found"
                    })

            elif message_type == "unsubscribe":
                # Unsubscribe from a session
                session_id = message.get("sessionId")
                session_manager.unsubscribe(session_id, websocket)
                if websocket in active_connections:
                    del active_connections[websocket]
                current_session_id = None
                await websocket.send_json({
                    "type": "unsubscribed",
                    "sessionId": session_id
                })

            else:
                await websocket.send_json({
                    "type": "error",
                    "error": f"Unknown message type: {message_type}"
                })

    except WebSocketDisconnect:
        print(f"[WebSocket] Client disconnected")
    except Exception as e:
        print(f"[WebSocket] Error: {e}")
    finally:
        # Cleanup
        if current_session_id:
            session_manager.unsubscribe(current_session_id, websocket)
        if websocket in active_connections:
            del active_connections[websocket]


async def process_claude_message(session_id: str, content: str, resume_session_id: str = None):
    """Process a message through Claude and broadcast responses"""
    try:
        session = session_manager.sessions[session_id]
        session.message_count += 1

        print(f"[Claude] Processing message {session.message_count} for session {session_id}")

        # Stream messages from Claude
        async for message in claude_client.query_stream(
            prompt=content,
            session_id=session_id,
            resume_session_id=resume_session_id
        ):
            # Capture SDK session ID for multi-turn
            if message.get("type") == "system" and message.get("subtype") == "init":
                session.sdk_session_id = message.get("session_id")
                print(f"[Claude] Captured SDK session ID: {session.sdk_session_id}")

            # Transform message to frontend format
            ws_message = transform_sdk_message(message, session_id)

            if ws_message:
                await session_manager.broadcast_to_session(session_id, ws_message)

            # Check if conversation ended
            if message.get("type") == "result":
                print(f"[Claude] Result received for session {session_id}")

    except Exception as e:
        print(f"[Claude] Error processing message: {e}")
        await session_manager.broadcast_to_session(session_id, {
            "type": "error",
            "error": str(e),
            "sessionId": session_id
        })


def transform_sdk_message(sdk_message: Dict[str, Any], session_id: str) -> Dict[str, Any]:
    """Transform SDK message format to frontend format"""
    msg_type = sdk_message.get("type")

    if msg_type == "assistant":
        # Handle assistant message
        message_obj = sdk_message.get("message", {})
        content = message_obj.get("content", "")

        if isinstance(content, str):
            return {
                "type": "assistant_message",
                "content": content,
                "sessionId": session_id
            }
        elif isinstance(content, list):
            # Handle content blocks
            messages = []
            for block in content:
                if block.get("type") == "text":
                    messages.append({
                        "type": "assistant_message",
                        "content": block.get("text", ""),
                        "sessionId": session_id
                    })
                elif block.get("type") == "tool_use":
                    messages.append({
                        "type": "tool_use",
                        "toolName": block.get("name"),
                        "toolId": block.get("id"),
                        "toolInput": block.get("input"),
                        "sessionId": session_id
                    })
                elif block.get("type") == "tool_result":
                    messages.append({
                        "type": "tool_result",
                        "toolUseId": block.get("tool_use_id"),
                        "content": block.get("content"),
                        "isError": block.get("is_error", False),
                        "sessionId": session_id
                    })
            # Return first message, others will be broadcasted separately
            return messages[0] if messages else None

    elif msg_type == "result":
        if sdk_message.get("subtype") == "success":
            return {
                "type": "result",
                "success": True,
                "result": sdk_message.get("result"),
                "cost": sdk_message.get("total_cost_usd"),
                "duration": sdk_message.get("duration_ms"),
                "sessionId": session_id
            }
        else:
            return {
                "type": "result",
                "success": False,
                "error": sdk_message.get("subtype"),
                "sessionId": session_id
            }

    elif msg_type == "system":
        return {
            "type": "system",
            "subtype": sdk_message.get("subtype"),
            "sessionId": session_id,
            "data": sdk_message
        }

    elif msg_type == "error":
        return {
            "type": "error",
            "error": sdk_message.get("error", "Unknown error"),
            "details": sdk_message.get("details", ""),
            "sessionId": session_id
        }

    return None


if __name__ == "__main__":
    import uvicorn
    print(f"Starting Python backend on {PYTHON_BACKEND_HOST}:{PYTHON_BACKEND_PORT}")
    uvicorn.run(
        app,
        host=PYTHON_BACKEND_HOST,
        port=PYTHON_BACKEND_PORT,
        log_level="info"
    )
