"""
GTFS Service - Handles train schedules, live positions, delays, and ETA generation
Mock GTFS-Realtime feed with realistic Pune Metro data
"""
import random
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "dbname": "transit_sync", "user": "postgres",
    "password": "postgres", "host": "localhost", "port": 5433
}

ROUTE_STOPS = [
    "PCMC", "SANT_TUKARAM", "BHOSARI", "KASARWADI", "PIMPRI",
    "CHINCHWAD", "AKURDI", "NIGDI",                          # Line 1 (PCMC to Nigdi)
    "SWARGATE", "MARKET_YARD", "SHIVAJINAGAR", "CIVIL_COURT",
    "PUNE_STATION", "RUBY_HALL", "RANGE_HILLS",               # Line 2 (Swargate to Range Hills)
]


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def get_live_trains() -> List[Dict]:
    """Fetch all trains with ETA info"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT t.trip_id, t.route_id, t.station_id, t.scheduled_arrival,
                   t.estimated_arrival, t.delay_minutes, t.passenger_load, t.status,
                   s.name as station_name, s.lat, s.lon
            FROM gtfs_trains t
            LEFT JOIN stations s ON t.station_id = s.id
            WHERE t.estimated_arrival > NOW() - INTERVAL '5 minutes'
              AND t.estimated_arrival < NOW() + INTERVAL '90 minutes'
            ORDER BY t.estimated_arrival ASC
            LIMIT 30
        """)
        rows = cur.fetchall()
        cols = ["trip_id", "route_id", "station_id", "scheduled_arrival",
                "estimated_arrival", "delay_minutes", "passenger_load", "status",
                "station_name", "lat", "lon"]
        trains = []
        now_utc = datetime.utcnow()
        for row in rows:
            t = dict(zip(cols, row))
            # Refresh old ETAs to be "soon" if they have already passed to show life
            est_dt = t["estimated_arrival"]
            if est_dt < now_utc - timedelta(minutes=2):
                # Simulated refreshing: make it arrive in 5-20 mins
                est_dt = now_utc + timedelta(minutes=random.randint(4, 18))
                t["estimated_arrival"] = est_dt
                t["status"] = "on_time"

            t["scheduled_arrival"] = t["scheduled_arrival"].isoformat() if t["scheduled_arrival"] else None
            t["estimated_arrival"] = est_dt.isoformat() if est_dt else None
            
            t["minutes_until_arrival"] = max(0, int((est_dt - now_utc).total_seconds() / 60))
            trains.append(t)
        cur.close()
        conn.close()
        return trains
    except Exception as e:
        print(f"GTFS error: {e}")
        return _mock_trains()


def get_station_eta(station_id: str) -> Optional[Dict]:
    """Get next train ETA for a specific station"""
    trains = get_live_trains()
    for t in trains:
        if t["station_id"] == station_id:
            return t
    return None


def simulate_train_arrival(station_id: str, delay_minutes: float = 0.0,
                            passenger_load: int = None) -> Dict:
    """Simulate a train arriving at a station (updates DB)"""
    if passenger_load is None:
        passenger_load = random.randint(100, 350)
    try:
        conn = get_conn()
        cur = conn.cursor()
        now = datetime.utcnow()
        scheduled = now + timedelta(minutes=random.randint(5, 15))
        estimated = scheduled + timedelta(minutes=delay_minutes)
        trip_id = f"SIM_{station_id}_{int(now.timestamp())}"
        cur.execute("""
            INSERT INTO gtfs_trains (trip_id, route_id, station_id, scheduled_arrival,
                                     estimated_arrival, delay_minutes, passenger_load, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (trip_id) DO UPDATE SET
                estimated_arrival = EXCLUDED.estimated_arrival,
                delay_minutes = EXCLUDED.delay_minutes,
                passenger_load = EXCLUDED.passenger_load
        """, (trip_id, "PUNE_METRO_L1", station_id, scheduled, estimated,
              delay_minutes, passenger_load,
              "delayed" if delay_minutes > 3 else "on_time"))
        conn.commit()
        cur.close()
        conn.close()
        return {
            "trip_id": trip_id,
            "station_id": station_id,
            "scheduled_arrival": scheduled.isoformat(),
            "estimated_arrival": estimated.isoformat(),
            "delay_minutes": delay_minutes,
            "passenger_load": passenger_load,
            "minutes_until_arrival": int((estimated - datetime.utcnow()).total_seconds() / 60),
            "status": "delayed" if delay_minutes > 3 else "on_time",
        }
    except Exception as e:
        print(f"Simulate arrival error: {e}")
        return {}


def _mock_trains() -> List[Dict]:
    """Fallback mock trains when DB unavailable"""
    now = datetime.utcnow()
    stations = [
        {"id": "PUNE_STATION", "name": "Pune Railway Station", "lat": 18.5295, "lon": 73.8740},
        {"id": "SHIVAJINAGAR", "name": "Shivajinagar", "lat": 18.5308, "lon": 73.8474},
        {"id": "SWARGATE", "name": "Swargate", "lat": 18.5026, "lon": 73.8540},
    ]
    trains = []
    for i, s in enumerate(stations):
        eta = now + timedelta(minutes=5 + i * 8)
        delay = random.uniform(0, 5)
        trains.append({
            "trip_id": f"MOCK_{s['id']}_{i}",
            "route_id": "PUNE_METRO_L1",
            "station_id": s["id"],
            "station_name": s["name"],
            "lat": s["lat"],
            "lon": s["lon"],
            "scheduled_arrival": eta.isoformat(),
            "estimated_arrival": (eta + timedelta(minutes=delay)).isoformat(),
            "delay_minutes": round(delay, 1),
            "passenger_load": random.randint(80, 280),
            "status": "delayed" if delay > 3 else "on_time",
            "minutes_until_arrival": 5 + i * 8,
        })
    return trains


def get_gtfs_feed_summary() -> Dict:
    """Summary stats for admin dashboard"""
    trains = get_live_trains()
    delayed = [t for t in trains if t["status"] == "delayed"]
    return {
        "total_active_trains": len(trains),
        "delayed_trains": len(delayed),
        "on_time_trains": len(trains) - len(delayed),
        "avg_delay_minutes": round(sum(t["delay_minutes"] for t in trains) / max(1, len(trains)), 1),
        "trains": trains[:10],
    }
# GTFS feed parser + train simulation
