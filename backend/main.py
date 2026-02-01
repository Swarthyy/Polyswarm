"""
PolySwarm 2.0 - War Room Backend
FastAPI server with WebSocket real-time communication
"""

import asyncio
import json
import random
from datetime import datetime
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="PolySwarm 2.0",
    description="High-frequency trading and AI consensus bot for Polymarket",
    version="2.0.0"
)

# CORS middleware for frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"[+] Client connected. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        print(f"[-] Client disconnected. Total: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        """Send message to all connected clients"""
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)
        
        # Clean up disconnected clients
        self.active_connections -= disconnected


manager = ConnectionManager()


async def heartbeat_loop():
    """Sends heartbeat with system status every second"""
    while True:
        # Simulate varying latency
        latency = random.randint(35, 75)
        
        payload = {
            "type": "heartbeat",
            "latency": f"{latency}ms",
            "active_cores": ["FLASH", "SWARM"],
            "timestamp": datetime.utcnow().isoformat(),
            "status": {
                "flash": {
                    "state": "ACTIVE",
                    "markets_scanning": random.randint(12, 24),
                    "opportunities": random.randint(0, 3)
                },
                "swarm": {
                    "state": "STANDBY",
                    "agents_ready": 3,
                    "consensus": None
                }
            }
        }
        
        await manager.broadcast(payload)
        await asyncio.sleep(1)


@app.on_event("startup")
async def startup_event():
    """Start background tasks on server startup"""
    asyncio.create_task(heartbeat_loop())
    print("=" * 50)
    print("  POLYSWARM 2.0 - WAR ROOM ONLINE")
    print("  WebSocket: ws://localhost:8000/ws")
    print("=" * 50)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "name": "PolySwarm 2.0",
        "status": "operational",
        "cores": {
            "flash": "active",
            "swarm": "standby"
        }
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "connections": len(manager.active_connections),
        "timestamp": datetime.utcnow().isoformat()
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for real-time dashboard updates"""
    await manager.connect(websocket)
    
    try:
        while True:
            # Keep connection alive, listen for client messages
            data = await websocket.receive_text()
            
            # Handle client commands (for future use)
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
