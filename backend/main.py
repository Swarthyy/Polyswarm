"""
PolySwarm 2.0 - War Room Backend
FastAPI server with WebSocket real-time communication
Integrates the Ingestion Engine for Reality Gap monitoring
"""

import asyncio
import json
import random
from datetime import datetime
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from core_flash.ingest import IngestionEngine

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
ingestion_engine: IngestionEngine = None


async def heartbeat_loop():
    """Sends heartbeat with system status every second"""
    while True:
        # Get real data from ingestion engine if available
        markets_scanning = 1 if ingestion_engine and ingestion_engine._running else 0
        opportunities = 0

        # Calculate opportunities based on gap
        if ingestion_engine:
            gap_data = ingestion_engine._calculate_gap()
            if gap_data and abs(gap_data.gap_percent) > 0.03:
                opportunities = 1

        # Simulate varying latency
        latency = random.randint(35, 75)

        payload = {
            "type": "heartbeat",
            "latency": f"{latency}ms",
            "active_cores": ["FLASH", "SWARM"],
            "timestamp": datetime.utcnow().isoformat(),
            "status": {
                "flash": {
                    "state": "ACTIVE" if ingestion_engine and ingestion_engine._running else "STANDBY",
                    "markets_scanning": markets_scanning,
                    "opportunities": opportunities
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


async def start_ingestion_engine():
    """Initialize and start the Ingestion Engine"""
    global ingestion_engine

    # Create engine with broadcast callback
    ingestion_engine = IngestionEngine(broadcast_callback=manager.broadcast)

    # Start the engine (this runs forever until stopped)
    await ingestion_engine.start()


@app.on_event("startup")
async def startup_event():
    """Start background tasks on server startup"""
    # Start heartbeat loop
    asyncio.create_task(heartbeat_loop())

    # Start the Ingestion Engine for Reality Gap monitoring
    asyncio.create_task(start_ingestion_engine())

    print("=" * 50)
    print("  POLYSWARM 2.0 - WAR ROOM ONLINE")
    print("  WebSocket: ws://localhost:8000/ws")
    print("  Ingestion Engine: ACTIVE")
    print("=" * 50)


@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown of background tasks"""
    global ingestion_engine
    if ingestion_engine:
        await ingestion_engine.stop()
    print("[SHUTDOWN] War Room offline")


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "name": "PolySwarm 2.0",
        "status": "operational",
        "cores": {
            "flash": "active",
            "swarm": "standby"
        },
        "ingestion": "active" if ingestion_engine and ingestion_engine._running else "inactive"
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "connections": len(manager.active_connections),
        "timestamp": datetime.utcnow().isoformat(),
        "ingestion_engine": {
            "running": ingestion_engine._running if ingestion_engine else False,
            "binance_connected": ingestion_engine.binance.last_price is not None if ingestion_engine else False,
            "polymarket_connected": ingestion_engine.polymarket.implied_price is not None if ingestion_engine else False
        }
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for real-time dashboard updates"""
    await manager.connect(websocket)

    try:
        while True:
            # Keep connection alive, listen for client messages
            data = await websocket.receive_text()

            # Handle client commands
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})

                # Add command to request current gap snapshot
                elif message.get("type") == "get_gap":
                    if ingestion_engine:
                        gap_data = ingestion_engine._calculate_gap()
                        if gap_data:
                            await websocket.send_json({
                                "type": "gap_snapshot",
                                "binance": gap_data.binance_price,
                                "poly_implied": gap_data.poly_implied,
                                "gap_percent": gap_data.gap_percent,
                                "latency_delta_ms": gap_data.latency_delta_ms
                            })

                # Kill Switch Command
                elif message.get("type") == "kill_switch":
                    action = message.get("action")
                    if ingestion_engine and ingestion_engine.executor:
                        if action == "DISABLE":
                            ingestion_engine.executor.disable_trading()
                            await manager.broadcast({
                                "type": "system_alert",
                                "message": "⚠️ KILL SWITCH ENGAGED - TRADING DISABLED",
                                "level": "CRITICAL"
                            })
                        elif action == "ENABLE":
                            ingestion_engine.executor.enable_trading()
                            await manager.broadcast({
                                "type": "system_alert",
                                "message": "✅ KILL SWITCH RELEASED - TRADING ENABLED",
                                "level": "INFO"
                            })
                        
                        # Send updated status
                        await websocket.send_json({
                            "type": "executor_status",
                            "status": ingestion_engine.executor.get_status()
                        })

            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/status/execution")
async def execution_status():
    """Get detailed execution engine status"""
    if not ingestion_engine or not ingestion_engine.executor:
        return {"status": "inactive", "message": "Executor not initialized"}
    
    return ingestion_engine.executor.get_status()
