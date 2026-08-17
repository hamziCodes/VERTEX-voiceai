import asyncio
import logging
from typing import Dict, Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        #empty dictionary to store active connections
        self.active_connections: Dict[str, WebSocket] = {}
        #asuncio.lock to ensure thread safety when accessing the active_connections dictionary
        self.lock = asyncio.Lock()

    async def connect(self, session_id: str, websocket: WebSocket):
        """Safely accepts and registers a new client connection."""
        # tell fastapi to accept the handshake and establish the WebSocket connection
        await websocket.accept()

        # lock and resgister the new connection in our active_connections dictionary
        async with self.lock:
            self.active_connections[session_id] = websocket
            
        logger.info(f"Session {session_id} successfully registered. Active connections: {len(self.active_connections)}")

    async def disconnect(self, session_id: str):
        """Safely removes a client connection."""
        async with self.lock:
            # .pop(key, None) deletes the key safely without crashing if it doesn't exist
            self.active_connections.pop(session_id, None)

        logger.info(f"Session {session_id} removed. Active connections: {len(self.active_connections)}")    

    async def get_connection(self, session_id: str) -> Optional[WebSocket]:
        """Retrieves a specific client's WebSocket connection by its session ID."""
        async with self.lock:
            return self.active_connections.get(session_id)
        
# Create a single, global instance of the ConnectionManager
connection_manager = ConnectionManager()
