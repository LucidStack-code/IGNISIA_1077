import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.models.db import init_db
from backend.routers import stations, vehicles, trains, metrics
from backend.schemas.payloads import BookRidePayload, TriggerDelayPayload
from backend.simulation.engine import SimulationEngine
from backend.websocket.hub import ConnectionHub

hub = ConnectionHub()
sim_engine = SimulationEngine(hub)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await sim_engine.start()
    app.state.sim_engine = sim_engine
    yield
    await sim_engine.stop()


app = FastAPI(title="TransitMind AI", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stations.router, prefix="/api")
app.include_router(vehicles.router, prefix="/api")
app.include_router(trains.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")


@app.get("/")
async def root():
    return {"service": "TransitMind AI", "status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await hub.connect(websocket)
    try:
        snapshot = await sim_engine.snapshot()
        await hub.send(websocket, snapshot)
        while True:
            message = await websocket.receive_text()
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")
            if msg_type == "TRIGGER_DEMO":
                result = await sim_engine.trigger_demo()
                await hub.send(websocket, {"type": "TRAIN_UPDATE", **result})
            elif msg_type == "TRIGGER_DELAY":
                payload = TriggerDelayPayload(**data)
                result = await sim_engine.trigger_delay(payload.train_id, payload.delay_minutes)
                await hub.send(websocket, {"type": "TRAIN_UPDATE", **result})
            elif msg_type == "BOOK_RIDE":
                payload = BookRidePayload(**data)
                result = await sim_engine.book_ride(payload.from_lat, payload.from_lng, payload.to_station_id)
                await hub.send(websocket, {"type": "BOOK_RIDE_RESULT", **result})
            elif msg_type == "REQUEST_SNAPSHOT":
                state = await sim_engine.snapshot()
                await hub.send(websocket, state)
            elif msg_type == "SET_SPEED":
                speed = int(data.get("speed", 1))
                sim_engine.speed_multiplier = max(1, min(speed, 5))
                await hub.send(websocket, {"type": "SPEED_UPDATED", "speed": sim_engine.speed_multiplier})
    except WebSocketDisconnect:
        hub.disconnect(websocket)
    except Exception:
        hub.disconnect(websocket)
