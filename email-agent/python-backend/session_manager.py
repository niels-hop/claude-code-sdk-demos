import asyncio
from typing import Dict, Set, Optional
from dataclasses import dataclass
import json
from datetime import datetime


@dataclass
class Session:
    """Represents a single Claude conversation session"""
    id: str
    sdk_session_id: Optional[str] = None
    message_count: int = 0
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class SessionManager:
    """Manages multiple Claude conversation sessions"""

    def __init__(self):
        self.sessions: Dict[str, Session] = {}
        self.subscribers: Dict[str, Set] = {}  # session_id -> set of websockets

    def generate_session_id(self) -> str:
        """Generate a unique session ID"""
        import time
        import random
        return f"session-{int(time.time() * 1000)}-{random.randint(1000, 9999)}"

    def get_or_create_session(self, session_id: Optional[str] = None) -> Session:
        """Get existing session or create a new one"""
        if session_id and session_id in self.sessions:
            return self.sessions[session_id]

        new_session_id = session_id or self.generate_session_id()
        session = Session(id=new_session_id)
        self.sessions[new_session_id] = session
        self.subscribers[new_session_id] = set()

        print(f"[SessionManager] Created new session: {new_session_id}")
        return session

    def subscribe(self, session_id: str, websocket) -> None:
        """Subscribe a websocket to a session"""
        if session_id not in self.subscribers:
            self.subscribers[session_id] = set()
        self.subscribers[session_id].add(websocket)
        print(f"[SessionManager] Subscribed websocket to session {session_id}")

    def unsubscribe(self, session_id: str, websocket) -> None:
        """Unsubscribe a websocket from a session"""
        if session_id in self.subscribers:
            self.subscribers[session_id].discard(websocket)
            print(f"[SessionManager] Unsubscribed websocket from session {session_id}")

    async def broadcast_to_session(self, session_id: str, message: dict) -> None:
        """Broadcast a message to all subscribers of a session"""
        if session_id not in self.subscribers:
            return

        message_str = json.dumps(message)
        disconnected = set()

        for websocket in self.subscribers[session_id]:
            try:
                await websocket.send_text(message_str)
            except Exception as e:
                print(f"[SessionManager] Error sending to websocket: {e}")
                disconnected.add(websocket)

        # Clean up disconnected websockets
        for ws in disconnected:
            self.subscribers[session_id].discard(ws)

    def get_active_sessions(self) -> list:
        """Get list of active session IDs"""
        return list(self.sessions.keys())

    def end_conversation(self, session_id: str) -> None:
        """End a conversation (reset SDK session ID)"""
        if session_id in self.sessions:
            self.sessions[session_id].sdk_session_id = None
            print(f"[SessionManager] Ended conversation for session {session_id}")

    def cleanup_session(self, session_id: str) -> None:
        """Clean up a session completely"""
        if session_id in self.sessions:
            del self.sessions[session_id]
        if session_id in self.subscribers:
            del self.subscribers[session_id]
        print(f"[SessionManager] Cleaned up session {session_id}")
