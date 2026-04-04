"""
Transit Sync - FastAPI Backend
Main application entry point with all routers
"""
import os
import asyncio
import json
import uuid
import random
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ── Lazy imports (graceful fallback if DB not available) ─────────────────────
try:
    from services.websocket_manager import manager
    from services.geofence_engine import (
        query_drivers_near_hotspot, query_all_drivers, update_driver_location,
        toggle_driver_availability, assign_driver_to_hotspot,
        upsert_hotspot, get_active_hotspots, update_driver_battery, get_charging_hubs,
        create_driver
    )
    from services.fleet_optimizer import greedy_assignment, surge_rebalance, real_time_match, proactive_rebalance_future
    from services.gtfs_service import (
        get_live_trains, get_station_eta, simulate_train_arrival, get_gtfs_feed_summary
    )
    from ml.demand_predictor import get_predictor
    DB_AVAILABLE = True
except Exception as e:
    print(f"⚠️  Some services unavailable: {e}")
    DB_AVAILABLE = False


# ── Pydantic Models ──────────────────────────────────────────────────────────
class RideRequestBody(BaseModel):
    passenger_name: str
    pickup_lat: float
    pickup_lon: float
    destination_lat: Optional[float] = None
    destination_lon: Optional[float] = None
    station_id: Optional[str] = None

class DriverLocationUpdate(BaseModel):
    driver_id: str
    lat: float
    lon: float

class DriverToggle(BaseModel):
    driver_id: str
    is_available: bool

class PredictRequest(BaseModel):
    station_id: str
    minutes_until_arrival: int = 10
    delay_minutes: float = 0.0
    weather: str = "clear"

class SimulateArrival(BaseModel):
    station_id: str
    delay_minutes: float = 0.0
    passenger_load: Optional[int] = None

class OptimizeFleet(BaseModel):
    radius_km: float = 5.0
    surge_mode: bool = False

class DriverCreateBody(BaseModel):
    name: str
    vehicle_type: str
    lat: float
    lon: float

class DisruptionBody(BaseModel):
    station_id: str
    intensity: float = 0.5

class ClearDisruptionBody(BaseModel):
    station_id: str


# ── App Lifecycle ────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Transit Sync backend starting...")
    if DB_AVAILABLE:
        # Start background simulation task
        asyncio.create_task(background_simulation())
    yield
    print("👋 Transit Sync backend shutting down")


app = FastAPI(
    title="Transit Sync API",
    description="Predictive Last-Mile Transit Synchronizer",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Background Simulation ────────────────────────────────────────────────────
async def background_simulation():
    """Periodically simulate driver movement and broadcast updates"""
    while True:
        try:
            await asyncio.sleep(8)  # Update every 8 seconds
            if not DB_AVAILABLE:
                continue

            # ── Battery & Movement Simulation (Twist 2) ────────────────────────
            all_drivers = query_all_drivers()
            hubs = get_charging_hubs()
            updated_count = 0
            
            for d in all_drivers:
                if not d.get("is_online"): continue
                
                battery = d.get("battery_level", 1.0)
                is_available = d.get("is_available")
                is_charging = d.get("is_charging", False)
                
                # 1. Deplete battery
                if not is_charging:
                    # Deplete faster if busy (on trip), slower if idle
                    depletion = random.uniform(0.002, 0.005) if not is_available else random.uniform(0.0005, 0.001)
                    battery = max(0.0, battery - depletion)

                # 2. Auto-Trip Completion (Simulation Polish)
                # If busy, randomly complete trip (~60s avg)
                if not is_available and not is_charging:
                    if random.random() > 0.85:
                        is_available = True
                        toggle_driver_availability(d["id"], True)

                # 3. Critical Battery Safety Net
                if battery < 0.05 and not is_available:
                    is_available = True
                    toggle_driver_availability(d["id"], True)
                
                # 4. Charging Logic
                if battery < 0.15 and is_available and not is_charging:
                    # Low battery! Find nearest hub
                    nearest_hub = None
                    min_dist = float('inf')
                    for h in hubs:
                        dist = ((d['lat']-h['lat'])**2 + (d['lon']-h['lon'])**2)**0.5
                        if dist < min_dist:
                            min_dist = dist
                            nearest_hub = h
                    
                    if nearest_hub:
                        # Move towards hub (0.001 deg ~ 100m)
                        step = 0.002
                        new_lat = d["lat"] + (1 if nearest_hub["lat"] > d["lat"] else -1) * min(step, abs(nearest_hub["lat"] - d["lat"]))
                        new_lon = d["lon"] + (1 if nearest_hub["lon"] > d["lon"] else -1) * min(step, abs(nearest_hub["lon"] - d["lon"]))
                        
                        # If reached hub
                        if min_dist < 0.001:
                            is_charging = True
                            battery = min(1.0, battery + 0.05) # Charge 5% per tick
                        
                        update_driver_location(d["id"], new_lat, new_lon)
                        update_driver_battery(d["id"], battery, is_charging)
                        updated_count += 1
                        continue

                if is_charging:
                    battery = min(1.0, battery + 0.08)
                    if battery >= 0.95: is_charging = False
                    update_driver_battery(d["id"], battery, is_charging)
                    updated_count += 1
                    continue

                # 5. Normal Jitter for available drivers
                if is_available and random.random() > 0.7:
                    new_lat = d["lat"] + random.uniform(-0.0003, 0.0003)
                    new_lon = d["lon"] + random.uniform(-0.0003, 0.0003)
                    update_driver_location(d["id"], new_lat, new_lon)
                    update_driver_battery(d["id"], battery, is_charging)
                    updated_count += 1
                else:
                    # Just update battery
                    update_driver_battery(d["id"], battery, is_charging)

            # Broadcast ALL driver positions to admins
            refreshed_drivers = query_all_drivers()
            await manager.broadcast_to_admins({
                "type": "DRIVERS_UPDATE",
                "drivers": refreshed_drivers,
                "count": len(refreshed_drivers),
                "moved": updated_count
            })
        except Exception as e:
            print(f"Simulation error: {e}")
            await asyncio.sleep(10)


# ── Health ───────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status": "ok",
        "db_available": DB_AVAILABLE,
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }


# ── GTFS Routes ──────────────────────────────────────────────────────────────
@app.get("/api/trains")
def get_trains():
    if not DB_AVAILABLE:
        return {"trains": _mock_trains_data(), "total": 3}
    trains = get_live_trains()
    return {"trains": trains, "total": len(trains)}


@app.get("/api/gtfs/summary")
def gtfs_summary():
    if not DB_AVAILABLE:
        return {"total_active_trains": 5, "delayed_trains": 1, "on_time_trains": 4,
                "avg_delay_minutes": 1.2, "trains": []}
    return get_gtfs_feed_summary()


@app.post("/api/simulate/disruption")
async def trigger_disruption(body: DisruptionBody):
    station_id = body.station_id
    intensity = body.intensity
    predictor = get_predictor()
    predictor.ripple_engine.trigger_disruption(station_id, intensity)
    
    await manager.broadcast_to_admins({
        "type": "DISRUPTION_TRIGGERED",
        "station_id": station_id,
        "intensity": intensity,
        "message": f"🚨 Breakdown at {station_id}! Ripple demand expected downstream."
    })
    return {"status": "ok", "station_id": station_id}


@app.post("/api/simulate/clear")
async def clear_disruption(body: ClearDisruptionBody):
    station_id = body.station_id
    predictor = get_predictor()
    predictor.ripple_engine.clear_disruption(station_id)
    return {"status": "cleared", "station_id": station_id}


@app.post("/api/trains/simulate")
async def simulate_arrival(body: SimulateArrival):
    """
    Simulates a train arrival, triggers ML demand prediction,
    creates a hotspot, and broadcasts to all connected clients.
    """
    if not DB_AVAILABLE:
        # Fallback to mock behavior for UI demonstration if DB goes down
        pred = _mock_prediction(body.station_id)
        await manager.broadcast_to_admins({
            "type": "TRAIN_ARRIVAL_SIMULATED",
            "station_id": body.station_id,
            "prediction": pred,
            "message": f"🚆 Mock Simulation: {body.station_id}"
        })
        return {"status": "mock_simulated", "station_id": body.station_id, "prediction": pred}

    try:
        result = simulate_train_arrival(body.station_id, body.delay_minutes, body.passenger_load)
        if not result:
            raise HTTPException(status_code=500, detail="Simulation failed")

        # Trigger demand prediction and hotspot creation
        predictor = get_predictor()
        pred = predictor.predict(
            station_id=body.station_id,
            minutes_until_arrival=result.get("minutes_until_arrival", 10),
            delay_minutes=body.delay_minutes,
        )
        
        # Upsert hotspot
        stations_lat_lon = _get_station_coords(body.station_id)
        if stations_lat_lon:
            hotspot_id = upsert_hotspot(
                body.station_id, stations_lat_lon[0], stations_lat_lon[1],
                pred["predicted_passengers"], pred["confidence"]
            )
            
            # Notify admins and drivers
            await manager.broadcast_to_admins({
                "type": "TRAIN_ARRIVAL_SIMULATED",
                "station_id": body.station_id,
                "prediction": pred,
                "hotspot_id": hotspot_id,
                "train": result,
            })
            
            # Find nearby drivers and notify them too
            nearby = query_drivers_near_hotspot(stations_lat_lon[0], stations_lat_lon[1], 5.0)
            driver_ids = [d["id"] for d in nearby]
            if driver_ids:
                await manager.notify_hotspot_alert(driver_ids, {**pred, "station_name": body.station_id})

        return {"status": "ok", "train": result, "prediction": pred}
    except Exception as e:
        print(f"Simulation error: {e}")
        # Final fallback to ensure the UI feels responsive
        return {"status": "error", "message": str(e)}


# ── Demand Prediction ─────────────────────────────────────────────────────────
@app.get("/api/predict/{station_id}")
def predict_station(station_id: str):
    if not DB_AVAILABLE:
        return _mock_prediction(station_id)
    predictor = get_predictor()
    # Assume 10 min arrival for single station query
    return predictor.predict(station_id=station_id, minutes_until_arrival=10)


@app.post("/api/predict/demand")
def predict_demand(body: PredictRequest):
    if not DB_AVAILABLE:
        return _mock_prediction(body.station_id)
    predictor = get_predictor()
    pred = predictor.predict(
        station_id=body.station_id,
        minutes_until_arrival=body.minutes_until_arrival,
        delay_minutes=body.delay_minutes,
        weather=body.weather,
    )
    coords = _get_station_coords(body.station_id)
    if coords:
        pred["lat"], pred["lon"] = coords
    return pred


@app.get("/api/predict/all")
def predict_all_stations():
    """Predict demand for all stations based on upcoming trains"""
    if not DB_AVAILABLE:
        return {"predictions": _mock_all_predictions()}
    trains = get_live_trains()
    predictor = get_predictor()
    predictions = []
    seen = set()
    for train in trains[:15]:
        sid = train["station_id"]
        if sid in seen:
            continue
        seen.add(sid)
        pred = predictor.predict(
            station_id=sid,
            minutes_until_arrival=train.get("minutes_until_arrival", 10),
            delay_minutes=train.get("delay_minutes", 0),
        )
        pred["lat"] = train.get("lat", 18.5726)
        pred["lon"] = train.get("lon", 73.8546)
        pred["station_name"] = train.get("station_name", sid)
        predictions.append(pred)
    return {"predictions": predictions}


# ── Drivers ───────────────────────────────────────────────────────────────────
@app.get("/api/drivers")
def list_drivers(available_only: bool = False):
    if not DB_AVAILABLE:
        return {"drivers": _mock_drivers()}
    drivers = query_all_drivers()
    if available_only:
        drivers = [d for d in drivers if d.get("is_available") and d.get("is_online")]
    return {"drivers": drivers, "total": len(drivers)}


@app.patch("/api/drivers/{driver_id}/location")
async def update_location(driver_id: str, body: Dict[str, float]):
    lat, lon = body.get("lat"), body.get("lon")
    if not DB_AVAILABLE:
        return {"status": "ok"}
    success = update_driver_location(driver_id, lat, lon)
    if success:
        await manager.broadcast_to_admins({
            "type": "DRIVER_MOVED",
            "driver_id": driver_id,
            "lat": lat,
            "lon": lon,
        })
    return {"status": "ok" if success else "failed"}


@app.patch("/api/drivers/{driver_id}/status")
async def update_driver_status(driver_id: str, body: Dict[str, Any]):
    is_online = body.get("is_online")
    is_available = body.get("is_available")
    
    if not DB_AVAILABLE:
        return {"status": "ok"}
    
    # Simple toggle for now
    if is_available is not None:
        success = toggle_driver_availability(driver_id, is_available)
        if success:
            await manager.send_to_driver(driver_id, {
                "type": "AVAILABILITY_CHANGED",
                "is_available": is_available,
            })
            await manager.broadcast_to_admins({
                "type": "DRIVER_STATUS_CHANGED",
                "driver_id": driver_id,
                "is_available": is_available,
            })
        return {"status": "ok" if success else "failed"}
    
    return {"status": "ok"}


@app.get("/api/drivers/nearby")
def drivers_nearby(lat: float, lon: float, radius_km: float = 5.0,
                   vehicle_type: str = None):
    if not DB_AVAILABLE:
        return {"drivers": _mock_drivers()[:5]}
    drivers = query_drivers_near_hotspot(lat, lon, radius_km, vehicle_type=vehicle_type)
    return {"drivers": drivers, "radius_km": radius_km, "total": len(drivers)}


# ── Fleet Optimization ────────────────────────────────────────────────────────
@app.post("/api/fleet/optimize")
async def optimize_fleet(body: OptimizeFleet):
    if not DB_AVAILABLE:
        return {"assignments": [], "coverage": 0.8, "message": "Mock mode"}
    drivers = query_all_drivers()
    hotspots = get_active_hotspots()
    if not hotspots:
        return {"assignments": [], "coverage": 1.0, "message": "No active hotspots"}

    if body.surge_mode:
        # Twist 1: Proactive rebalancing for future surges (T+30)
        predictor = get_predictor()
        future_hotspots = []
        for h in hotspots:
            # Predict demand at this station 30 mins from now
            f_pred = predictor.predict(h["station_id"], minutes_until_arrival=30)
            future_hotspots.append({
                "station_id": h["station_id"],
                "lat": h["lat"], "lon": h["lon"],
                "predicted_passengers": f_pred["predicted_passengers"]
            })
        
        assignments = proactive_rebalance_future(drivers, future_hotspots)
        coverage = len(assignments) / max(1, len(future_hotspots))
        result_msg = f"🚀 Proactive Surge Mode: Pre-positioned for T+30 demand"
    else:
        assignments = greedy_assignment(drivers, hotspots, body.radius_km)
        coverage = len(assignments) / max(1, len(hotspots))
        result_msg = f"✅ Optimized {len(assignments)} assignments"

    # Notify assigned drivers
    for assignment in assignments:
        driver_id = assignment["driver_id"]
        await manager.send_to_driver(driver_id, {
            "type": "REPOSITIONING_REQUEST",
            "hotspot_lat": assignment["hotspot_lat"],
            "hotspot_lon": assignment["hotspot_lon"],
            "hotspot_station": assignment["hotspot_station_id"],
            "predicted_passengers": assignment["predicted_passengers"],
            "eta_minutes": assignment["eta_minutes"],
            "message": f"📍 Move to {assignment['hotspot_station_id']} — {assignment['predicted_passengers']} passengers predicted",
        })
        assign_driver_to_hotspot(driver_id, assignment["hotspot_station_id"])

    await manager.broadcast_to_admins({
        "type": "FLEET_OPTIMIZED",
        "assignments": assignments,
        "coverage": coverage,
    })

    return {
        "assignments": assignments,
        "coverage": round(coverage, 3),
        "message": result_msg,
        "drivers_assigned": len(assignments),
    }


@app.post("/api/drivers")
async def create_driver_endpoint(body: DriverCreateBody):
    from services.geofence_engine import create_driver
    if not DB_AVAILABLE:
        return {"status": "error", "message": "Database not available"}
    
    driver_id = f"DRV_{uuid.uuid4().hex[:8].upper()}"
    success = create_driver(driver_id, body.name, body.vehicle_type, body.lat, body.lon)
    
    if success:
        return {"status": "ok", "driver_id": driver_id}
    else:
        return {"status": "error", "message": "Failed to create driver"}


@app.get("/api/hubs")
def list_hubs():
    from services.geofence_engine import get_charging_hubs
    if not DB_AVAILABLE:
        return {"hubs": [
            {"id": 1, "name": "Pune Station Hub", "lat": 18.5280, "lon": 73.8735, "available_spots": 8},
            {"id": 2, "name": "Shivajinagar Hub", "lat": 18.5315, "lon": 73.8480, "available_spots": 5},
        ]}
    return {"hubs": get_charging_hubs()}


# ── Hotspots ──────────────────────────────────────────────────────────────────
@app.get("/api/hotspots")
def list_hotspots():
    if not DB_AVAILABLE:
        return {"hotspots": _mock_hotspots()}
    return {"hotspots": get_active_hotspots()}


@app.post("/api/hotspots/trigger")
async def trigger_hotspot(body: PredictRequest):
    """Manually trigger demand prediction + hotspot creation for a station"""
    if not DB_AVAILABLE:
        return {"status": "ok", "prediction": _mock_prediction(body.station_id)}
    predictor = get_predictor()
    pred = predictor.predict(
        station_id=body.station_id,
        minutes_until_arrival=body.minutes_until_arrival,
        delay_minutes=body.delay_minutes,
        weather=body.weather,
    )
    coords = _get_station_coords(body.station_id)
    if coords:
        pred["lat"], pred["lon"] = coords
        hotspot_id = upsert_hotspot(
            body.station_id, coords[0], coords[1],
            pred["predicted_passengers"], pred["confidence"], body.weather
        )
        pred["hotspot_id"] = hotspot_id

        # Find nearby drivers and notify
        nearby = query_drivers_near_hotspot(coords[0], coords[1], 5.0, limit=5)
        driver_ids = [d["id"] for d in nearby]
        await manager.notify_hotspot_alert(driver_ids, {
            **pred,
            "station_name": body.station_id,
        })
        pred["notified_drivers"] = len(driver_ids)

    await manager.broadcast_to_admins({
        "type": "HOTSPOT_TRIGGERED",
        "prediction": pred,
    })
    return {"status": "ok", "prediction": pred}


# ── Ride Requests ──────────────────────────────────────────────────────────────
@app.post("/api/rides/request")
async def create_ride_request(body: RideRequestBody):
    request_id = f"REQ_{uuid.uuid4().hex[:8].upper()}"
    if not DB_AVAILABLE:
        return {
            "request_id": request_id,
            "status": "pending",
            "matched_driver": _mock_drivers()[0],
        }
    import psycopg2
    from db.init_db import DB_CONFIG
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ride_requests (id, passenger_name, pickup_location, pickup_lat, pickup_lon,
                                       destination_lat, destination_lon, station_id, status)
            VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s, %s, 'pending')
        """, (request_id, body.passenger_name, body.pickup_lon, body.pickup_lat,
              body.pickup_lat, body.pickup_lon, body.destination_lat, body.destination_lon,
              body.station_id))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Ride request error: {e}")

    # Real-time match
    drivers = query_all_drivers()
    available = [d for d in drivers if d.get("is_available") and d.get("is_online")]
    match = real_time_match(
        {"pickup_lat": body.pickup_lat, "pickup_lon": body.pickup_lon},
        available,
    )
    if match:
        toggle_driver_availability(match["id"], False)
        await manager.notify_ride_matched(match["id"], {
            "request_id": request_id,
            "passenger_name": body.passenger_name,
            "pickup_lat": body.pickup_lat,
            "pickup_lon": body.pickup_lon,
        })
        await manager.broadcast_to_admins({
            "type": "RIDE_MATCHED",
            "request_id": request_id,
            "driver_id": match["id"],
            "eta_minutes": match.get("eta_minutes", 5),
        })
        return {"request_id": request_id, "status": "matched", "driver": match}

    return {"request_id": request_id, "status": "pending", "message": "Searching for driver..."}


@app.get("/api/rides/{ride_id}")
async def get_ride_status(ride_id: str):
    # Mock status for now
    return {
        "ride_id": ride_id,
        "status": "matched",
        "driver": _mock_drivers()[0],
        "eta_minutes": 4
    }


@app.post("/api/rides/{ride_id}/complete")
async def complete_ride(ride_id: str):
    await manager.broadcast_to_admins({
        "type": "RIDE_COMPLETED",
        "ride_id": ride_id,
    })
    return {"status": "ok"}


@app.get("/api/rides/stats")
def ride_stats():
    """Stats for admin dashboard"""
    try:
        import psycopg2
        DB_CONFIG = {"dbname": "transit_sync", "user": "postgres",
                     "password": "postgres", "host": "localhost", "port": 5433}
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'matched') as matched,
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'completed') as completed,
                COUNT(*) as total,
                AVG(wait_time_seconds) FILTER (WHERE wait_time_seconds IS NOT NULL) as avg_wait
            FROM ride_requests
            WHERE created_at > NOW() - INTERVAL '24 hours'
        """)
        row = cur.fetchone()
        cur.close()
        conn.close()
        return {
            "matched": row[0] or 0, "pending": row[1] or 0,
            "completed": row[2] or 0, "total": row[3] or 0,
            "avg_wait_seconds": round(float(row[4] or 0), 1),
            "match_rate": round((row[0] or 0) / max(1, row[3] or 1), 3),
        }
    except:
        return {"matched": 24, "pending": 3, "completed": 47, "total": 74,
                "avg_wait_seconds": 187, "match_rate": 0.96}


# ── Stations ──────────────────────────────────────────────────────────────────
@app.get("/api/stations")
def list_stations():
    try:
        import psycopg2
        DB_CONFIG = {"dbname": "transit_sync", "user": "postgres",
                     "password": "postgres", "host": "localhost", "port": 5433}
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT id, name, lat, lon, zone, avg_daily_passengers FROM stations ORDER BY name")
        rows = cur.fetchall()
        cols = ["id", "name", "lat", "lon", "zone", "avg_daily_passengers"]
        stations = [dict(zip(cols, row)) for row in rows]
        cur.close()
        conn.close()
        return {"stations": stations}
    except:
        return {"stations": _mock_stations()}


# ── Admin Dashboard Stats ─────────────────────────────────────────────────────
@app.get("/api/admin/dashboard")
def admin_dashboard():
    drivers = query_all_drivers() if DB_AVAILABLE else _mock_drivers()
    hotspots = get_active_hotspots() if DB_AVAILABLE else _mock_hotspots()
    ride_s = ride_stats()
    ws_stats = manager.get_stats()

    online_drivers = [d for d in drivers if d.get("is_online")]
    available_drivers = [d for d in drivers if d.get("is_available") and d.get("is_online")]

    return {
        "fleet": {
            "total": len(drivers),
            "online": len(online_drivers),
            "available": len(available_drivers),
            "on_trip": len(online_drivers) - len(available_drivers),
            "by_type": {
                "auto": len([d for d in drivers if d.get("vehicle_type") == "auto"]),
                "cab": len([d for d in drivers if d.get("vehicle_type") == "cab"]),
                "ebike": len([d for d in drivers if d.get("vehicle_type") == "ebike"]),
            },
        },
        "hotspots": {
            "active": len(hotspots),
            "total_predicted_passengers": sum(h.get("predicted_passengers", 0) for h in hotspots),
        },
        "rides": ride_s,
        "websocket": ws_stats,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ── WebSocket Endpoints ────────────────────────────────────────────────────────
@app.websocket("/ws/driver/{driver_id}")
async def driver_websocket(websocket: WebSocket, driver_id: str):
    await manager.connect_driver(driver_id, websocket)
    try:
        await websocket.send_json({
            "type": "CONNECTED",
            "driver_id": driver_id,
            "message": f"✅ Driver {driver_id} connected to Transit Sync",
        })
        while True:
            data = await websocket.receive_json()
            # Handle incoming messages
            msg_type = data.get("type")
            if msg_type == "LOCATION_UPDATE":
                if DB_AVAILABLE:
                    update_driver_location(driver_id, data["lat"], data["lon"])
                await manager.broadcast_to_admins({
                    "type": "DRIVER_MOVED",
                    "driver_id": driver_id,
                    "lat": data["lat"],
                    "lon": data["lon"],
                })
            elif msg_type == "PING":
                await websocket.send_json({"type": "PONG"})
    except WebSocketDisconnect:
        manager.disconnect_driver(driver_id)
        print(f"Driver {driver_id} disconnected")


@app.websocket("/ws/passenger/{request_id}")
async def passenger_websocket(websocket: WebSocket, request_id: str):
    await manager.connect_passenger(request_id, websocket)
    try:
        await websocket.send_json({
            "type": "CONNECTED",
            "request_id": request_id,
            "message": "✅ Connected to Transit Sync",
        })
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "PING":
                await websocket.send_json({"type": "PONG"})
    except WebSocketDisconnect:
        manager.disconnect_passenger(request_id)


@app.websocket("/ws/admin")
async def admin_websocket(websocket: WebSocket):
    await manager.connect_admin(websocket)
    try:
        await websocket.send_json({
            "type": "CONNECTED",
            "message": "✅ Admin connected to Transit Sync",
        })
        # Send initial state
        if DB_AVAILABLE:
            drivers = query_all_drivers()
            hotspots = get_active_hotspots()
            await websocket.send_json({
                "type": "INITIAL_STATE",
                "drivers": drivers,
                "hotspots": hotspots,
            })
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "PING":
                await websocket.send_json({"type": "PONG"})
    except WebSocketDisconnect:
        manager.disconnect_admin(websocket)


# ── Mock Data Helpers ──────────────────────────────────────────────────────────
PUNE_STATIONS = [
    {"id": "PCMC", "lat": 18.6279, "lon": 73.8008},
    {"id": "PUNE_STATION", "lat": 18.5295, "lon": 73.8740},
    {"id": "SHIVAJINAGAR", "lat": 18.5308, "lon": 73.8474},
    {"id": "SWARGATE", "lat": 18.5026, "lon": 73.8540},
    {"id": "CHINCHWAD", "lat": 18.6452, "lon": 73.7997},
]
PUNE_STATION_MAP = {s["id"]: (s["lat"], s["lon"]) for s in PUNE_STATIONS}


def _get_station_coords(station_id: str):
    return PUNE_STATION_MAP.get(station_id)


def _mock_drivers():
    import random
    return [{"id": f"DRV_{i:03d}", "name": f"Driver {i}", "vehicle_type": ["auto","cab","ebike"][i%3],
             "lat": 18.5726 + random.uniform(-0.05,0.05),
             "lon": 73.8546 + random.uniform(-0.05,0.05),
             "is_online": True, "is_available": i % 3 != 0,
             "rating": round(3.8 + random.random(), 1)} for i in range(1, 11)]


def _mock_stations():
    return [
        {"id": "PUNE_STATION", "name": "Pune Railway Station", "lat": 18.5295, "lon": 73.8740, "zone": "D"},
        {"id": "SHIVAJINAGAR", "name": "Shivajinagar", "lat": 18.5308, "lon": 73.8474, "zone": "C"},
        {"id": "SWARGATE", "name": "Swargate", "lat": 18.5026, "lon": 73.8540, "zone": "C"},
    ]


def _mock_hotspots():
    return [
        {"id": 1, "station_id": "PUNE_STATION", "station_name": "Pune Railway Station",
         "lat": 18.5295, "lon": 73.8740, "predicted_passengers": 180, "confidence": 0.87},
        {"id": 2, "station_id": "SHIVAJINAGAR", "station_name": "Shivajinagar",
         "lat": 18.5308, "lon": 73.8474, "predicted_passengers": 120, "confidence": 0.82},
    ]


def _mock_prediction(station_id: str) -> dict:
    return {
        "station_id": station_id,
        "predicted_passengers": random.randint(80, 250),
        "confidence": round(random.uniform(0.75, 0.92), 2),
        "xgboost_estimate": random.randint(75, 230),
        "lstm_trend_multiplier": round(random.uniform(0.9, 1.2), 3),
        "peak_label": "Morning Peak",
        "time_window_start": datetime.utcnow().isoformat(),
        "time_window_end": (datetime.utcnow() + timedelta(minutes=15)).isoformat(),
    }


def _mock_trains_data():
    now = datetime.utcnow()
    return [
        {"trip_id": "MOCK_001", "station_id": "PUNE_STATION", "station_name": "Pune Railway Station",
         "lat": 18.5295, "lon": 73.8740, "delay_minutes": 2.0, "passenger_load": 220,
         "status": "on_time", "minutes_until_arrival": 8,
         "estimated_arrival": (now + timedelta(minutes=8)).isoformat()},
        {"trip_id": "MOCK_002", "station_id": "SHIVAJINAGAR", "station_name": "Shivajinagar",
         "lat": 18.5308, "lon": 73.8474, "delay_minutes": 0.0, "passenger_load": 150,
         "status": "on_time", "minutes_until_arrival": 12,
         "estimated_arrival": (now + timedelta(minutes=12)).isoformat()},
    ]


def _mock_all_predictions():
    stations = [
        ("PUNE_STATION", "Pune Railway Station", 18.5295, 73.8740),
        ("SHIVAJINAGAR", "Shivajinagar", 18.5308, 73.8474),
        ("SWARGATE", "Swargate", 18.5026, 73.8540),
        ("PCMC", "PCMC", 18.6279, 73.8008),
        ("CHINCHWAD", "Chinchwad", 18.6452, 73.7997),
    ]
    return [
        {"station_id": s[0], "station_name": s[1], "lat": s[2], "lon": s[3],
         "predicted_passengers": random.randint(60, 280),
         "confidence": round(random.uniform(0.75, 0.93), 2),
         "peak_label": "Morning Peak",
         "time_window_start": datetime.utcnow().isoformat()}
        for s in stations
    ]


@app.post("/api/simulate/recharge-all")
async def recharge_all_fleet():
    """Emergency 'God-Mode' for hackathon demo: Recharges all drivers to 100%"""
    if not DB_AVAILABLE:
        return {"status": "error", "message": "DB not available"}
    import psycopg2
    from db.init_db import DB_CONFIG
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            UPDATE drivers_live 
            SET battery_level = 1.0, is_charging = FALSE, is_available = TRUE, is_online = TRUE, updated_at = NOW()
        """)
        conn.commit()
        cur.close()
        conn.close()
        await manager.broadcast_to_admins({
            "type": "FLEET_RECHARGED",
            "message": "⚡ Emergency Fleet Recharge initiated by Admin!"
        })
        return {"status": "ok", "message": "All drivers recharged to 100% and set to Available"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
# FastAPI app + all API routes + WebSocket endpoints
