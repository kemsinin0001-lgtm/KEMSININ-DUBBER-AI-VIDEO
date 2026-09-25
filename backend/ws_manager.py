import asyncio
import json
from typing import List, Dict, Any
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.job_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def connect_job(self, websocket: WebSocket, job_id: str):
        await websocket.accept()
        if job_id not in self.job_connections:
            self.job_connections[job_id] = []
        self.job_connections[job_id].append(websocket)

    def disconnect_job(self, websocket: WebSocket, job_id: str):
        if job_id in self.job_connections and websocket in self.job_connections[job_id]:
            self.job_connections[job_id].remove(websocket)
            if not self.job_connections[job_id]:
                del self.job_connections[job_id]

    async def broadcast_job(self, job_id: str, message: Dict[str, Any]):
        dead = []
        payload = json.dumps(message) if not isinstance(message, str) else message
        conns = self.job_connections.get(job_id, [])
        for connection in conns:
            try:
                await connection.send_text(payload)
            except Exception:
                dead.append(connection)
        for d in dead:
            if d in conns:
                conns.remove(d)

        # Also mirror to general connections
        for conn in self.active_connections:
            try:
                await conn.send_text(payload)
            except Exception:
                pass

    async def broadcast(self, message: Dict[str, Any]):
        dead_connections = []
        payload = json.dumps(message) if not isinstance(message, str) else message
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception:
                dead_connections.append(connection)
        for dc in dead_connections:
            if dc in self.active_connections:
                self.active_connections.remove(dc)

    async def send_progress(self, stage: str, percent: float, detail: str = "", extra: Dict[str, Any] = None):
        msg = {
            "type": "progress",
            "stage": stage,
            "percent": round(percent, 1),
            "detail": detail
        }
        if extra:
            msg.update(extra)
        await self.broadcast(msg)

    async def send_status(self, status: str, detail: str = "", extra: Dict[str, Any] = None):
        msg = {
            "type": "status",
            "status": status,
            "detail": detail
        }
        if extra:
            msg.update(extra)
        await self.broadcast(msg)

    async def send_error(self, message: str, stage: str = ""):
        msg = {
            "type": "error",
            "message": message,
            "stage": stage
        }
        await self.broadcast(msg)

manager = ConnectionManager()
