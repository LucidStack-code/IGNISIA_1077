"""
Geofence Trigger Engine
Queries drivers within radius using PostGIS, ranks them, triggers WS notifications
"""
import psycopg2
import os
from typing import List, Dict, Tuple
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "dbname": "transit_sync", "user": "postgres",
    "password": "postgres", "host": "localhost", "port": 5433
}


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def query_drivers_near_hotspot(
    lat: float,
    lon: float,
    radius_km: float = 5.0,
    limit: int = 20,
    vehicle_type: str = None,
) -> List[Dict]:
    """
    PostGIS query to find available drivers within radius_km of a hotspot.
    Ranked by: distance ASC, idle_time DESC, rating DESC
    """
    try:
        conn = get_conn()
        cur = conn.cursor()
        type_filter = "AND vehicle_type = %s" if vehicle_type else ""
        params = [lon, lat, radius_km * 1000]
        if vehicle_type:
            params.append(vehicle_type)
        params.append(limit)

        cur.execute(f"""
            SELECT
                d.id, d.name, d.vehicle_type, d.lat, d.lon,
                d.is_online, d.is_available, d.rating, d.idle_since,
                d.assigned_hotspot,
                ST_Distance(
                    d.location::geography,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                ) / 1000.0 AS distance_km,
                EXTRACT(EPOCH FROM (NOW() - d.idle_since)) / 60 AS idle_minutes
            FROM drivers_live d
            WHERE d.is_online = TRUE
              AND d.is_available = TRUE
              {type_filter}
              AND ST_DWithin(
                    d.location::geography,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                    %s
              )
            ORDER BY
                distance_km ASC,
                idle_minutes DESC,
                d.rating DESC
            LIMIT %s
        """, [lon, lat] + ([vehicle_type] if vehicle_type else []) + [lon, lat, radius_km * 1000, limit])

        rows = cur.fetchall()
        cols = ["id", "name", "vehicle_type", "lat", "lon", "is_online",
                "is_available", "rating", "idle_since", "assigned_hotspot",
                "distance_km", "idle_minutes"]
        drivers = []
        for row in rows:
            d = dict(zip(cols, row))
            if d["idle_since"]:
                d["idle_since"] = d["idle_since"].isoformat()
            d["distance_km"] = round(float(d["distance_km"]), 3)
            d["idle_minutes"] = round(float(d["idle_minutes"]), 1)
            d["eta_minutes"] = round(float(d["distance_km"]) / 24 * 60, 1)
            drivers.append(d)
        cur.close()
        conn.close()
        return drivers
    except Exception as e:
        print(f"Geofence query error: {e}")
        return []


def query_all_drivers() -> List[Dict]:
    """Get all drivers for map display"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, vehicle_type, lat, lon, is_online, is_available,
                   rating, idle_since, assigned_hotspot, updated_at
            FROM drivers_live
            ORDER BY updated_at DESC
        """)
        rows = cur.fetchall()
        cols = ["id", "name", "vehicle_type", "lat", "lon", "is_online",
                "is_available", "rating", "idle_since", "assigned_hotspot", "updated_at"]
        drivers = []
        for row in rows:
            d = dict(zip(cols, row))
            for k in ["idle_since", "updated_at"]:
                if d[k]:
                    d[k] = d[k].isoformat()
            drivers.append(d)
        cur.close()
        conn.close()
        return drivers
    except Exception as e:
        print(f"Query drivers error: {e}")
        return []


def update_driver_location(driver_id: str, lat: float, lon: float) -> bool:
    """Update driver position in PostGIS"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE drivers_live
            SET lat = %s, lon = %s,
                location = ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                updated_at = NOW()
            WHERE id = %s
        """, (lat, lon, lon, lat, driver_id))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Update location error: {e}")
        return False


def toggle_driver_availability(driver_id: str, is_available: bool) -> bool:
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE drivers_live
            SET is_available = %s, is_online = %s,
                idle_since = CASE WHEN %s THEN NOW() ELSE idle_since END,
                updated_at = NOW()
            WHERE id = %s
        """, (is_available, is_available, is_available, driver_id))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Toggle availability error: {e}")
        return False


def assign_driver_to_hotspot(driver_id: str, hotspot_station_id: str) -> bool:
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE drivers_live
            SET assigned_hotspot = %s, is_available = FALSE, updated_at = NOW()
            WHERE id = %s
        """, (hotspot_station_id, driver_id))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Assign hotspot error: {e}")
        return False


def upsert_hotspot(station_id: str, lat: float, lon: float,
                   predicted_passengers: int, confidence: float,
                   weather: str = "clear") -> int:
    """Insert or update a predicted hotspot, return its ID"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        # Deactivate old hotspots for this station
        cur.execute("""
            UPDATE hotspots_predicted SET is_active = FALSE
            WHERE station_id = %s AND is_active = TRUE
        """, (station_id,))
        # Insert new hotspot
        cur.execute("""
            INSERT INTO hotspots_predicted
                (station_id, location, lat, lon, predicted_passengers,
                 time_window_start, time_window_end, confidence, weather, is_active)
            VALUES (%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s,
                    NOW(), NOW() + INTERVAL '15 minutes', %s, %s, TRUE)
            RETURNING id
        """, (station_id, lon, lat, lat, lon, predicted_passengers, confidence, weather))
        hotspot_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return hotspot_id
    except Exception as e:
        print(f"Upsert hotspot error: {e}")
        return -1


def get_active_hotspots() -> List[Dict]:
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT h.id, h.station_id, h.lat, h.lon, h.predicted_passengers,
                   h.time_window_start, h.time_window_end, h.confidence, h.weather,
                   s.name as station_name
            FROM hotspots_predicted h
            LEFT JOIN stations s ON h.station_id = s.id
            WHERE h.is_active = TRUE
              AND h.time_window_end > NOW()
            ORDER BY h.predicted_passengers DESC
        """)
        rows = cur.fetchall()
        cols = ["id", "station_id", "lat", "lon", "predicted_passengers",
                "time_window_start", "time_window_end", "confidence", "weather", "station_name"]
        hotspots = []
        for row in rows:
            h = dict(zip(cols, row))
            for k in ["time_window_start", "time_window_end"]:
                if h[k]:
                    h[k] = h[k].isoformat()
            hotspots.append(h)
        cur.close()
        conn.close()
        return hotspots
    except Exception as e:
        print(f"Get hotspots error: {e}")
        return []
