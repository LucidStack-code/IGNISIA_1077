# WS connection manager (driver/passenger/admin rooms)
"""
WebSocket Connection Manager for real-time notifications
Handles driver alerts, passenger tracking, and admin broadcasts
"""
import json
import asyncio
from typing import Dict, List, Set
from fastapi import WebSocket
from datetime import datetime


class ConnectionManager:
    def __init__(self):
        # Separate rooms for different client types
        self.driver_connections: Dict[str, WebSocket] = {}    # driver_id → ws
        self.passenger_connections: Dict[str, WebSocket] = {} # request_id → ws
        self.admin_connections: Set[WebSocket] = set()

    async def connect_driver(self, driver_id: str, websocket: WebSocket):
        await websocket.accept()
        self.driver_connections[driver_id] = websocket
        print(f"🔌 Driver {driver_id} connected via WebSocket")

    async def connect_passenger(self, request_id: str, websocket: WebSocket):
        await websocket.accept()
        self.passenger_connections[request_id] = websocket
        print(f"🔌 Passenger {request_id} connected via WebSocket")

    async def connect_admin(self, websocket: WebSocket):
        await websocket.accept()
        self.admin_connections.add(websocket)
        print(f"🔌 Admin connected. Total admins: {len(self.admin_connections)}")

    def disconnect_driver(self, driver_id: str):
        self.driver_connections.pop(driver_id, None)

    def disconnect_passenger(self, request_id: str):
        self.passenger_connections.pop(request_id, None)

    def disconnect_admin(self, websocket: WebSocket):
        self.admin_connections.discard(websocket)

    async def send_to_driver(self, driver_id: str, message: dict):
        ws = self.driver_connections.get(driver_id)
        if ws:
            try:
                await ws.send_json({**message, "timestamp": datetime.utcnow().isoformat()})
            except Exception:
                self.disconnect_driver(driver_id)

    async def send_to_passenger(self, request_id: str, message: dict):
        ws = self.passenger_connections.get(request_id)
        if ws:
            try:
                await ws.send_json({**message, "timestamp": datetime.utcnow().isoformat()})
            except Exception:
                self.disconnect_passenger(request_id)

    async def broadcast_to_drivers(self, message: dict, driver_ids: List[str] = None):
        """Broadcast to specific drivers or all connected drivers"""
        targets = driver_ids or list(self.driver_connections.keys())
        payload = {**message, "timestamp": datetime.utcnow().isoformat()}
        dead = []
        for driver_id in targets:
            ws = self.driver_connections.get(driver_id)
            if ws:
                try:
                    await ws.send_json(payload)
                except Exception:
                    dead.append(driver_id)
        for d in dead:
            self.disconnect_driver(d)

    async def broadcast_to_admins(self, message: dict):
        """Broadcast to all admin dashboards"""
        if not self.admin_connections:
            return
        payload = {**message, "timestamp": datetime.utcnow().isoformat()}
        dead = []
        for ws in self.admin_connections:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect_admin(ws)

    async def notify_hotspot_alert(self, driver_ids: List[str], hotspot: dict):
        """Send pre-positioning alert to drivers"""
        await self.broadcast_to_drivers({
            "type": "HOTSPOT_ALERT",
            "hotspot": hotspot,
            "message": f"🚨 High demand predicted at {hotspot.get('station_name', 'station')}. Move to hotspot!",
        }, driver_ids=driver_ids)

    async def notify_ride_matched(self, driver_id: str, ride: dict):
        """Notify driver of ride match"""
        await self.send_to_driver(driver_id, {
            "type": "RIDE_MATCHED",
            "ride": ride,
            "message": f"🎯 New ride request matched!",
        })

    async def notify_passenger_match(self, request_id: str, driver: dict):
        """Notify passenger their ride is confirmed"""
        await self.send_to_passenger(request_id, {
            "type": "DRIVER_ASSIGNED",
            "driver": driver,
            "message": f"✅ Driver {driver.get('name', '')} is on the way!",
        })

    def get_stats(self) -> dict:
        return {
            "connected_drivers": len(self.driver_connections),
            "connected_passengers": len(self.passenger_connections),
            "connected_admins": len(self.admin_connections),
        }


# Singleton
manager = ConnectionManager()
