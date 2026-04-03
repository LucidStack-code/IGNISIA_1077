from fastapi import WebSocket


class ConnectionHub:
    def __init__(self) -> None:
        self.connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections.discard(websocket)

    async def send(self, websocket: WebSocket, payload: dict) -> None:
        await websocket.send_json(payload)

    async def broadcast(self, payload: dict) -> None:
        stale = []
        for ws in list(self.connections):
            try:
                await ws.send_json(payload)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(ws)
