# DB init + seed data (15 stations, 20 drivers, GTFS trains)
"""
Initialize database with PostGIS extension, tables, indexes, and seed data
"""
import os
import sys
import psycopg2
from datetime import datetime, timedelta
import random
import json

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

DB_CONFIG = {
    "dbname": "transit_sync",
    "user": "postgres",
    "password": "postgres",
    "host": "localhost",
    "port": 5433,
}

# Pune Metro stations (real lat/lon)
STATIONS = [
    {"id": "PCMC", "name": "PCMC Station", "lat": 18.6279, "lon": 73.8008, "zone": "A"},
    {"id": "SANT_TUKARAM", "name": "Sant Tukaram Nagar", "lat": 18.6221, "lon": 73.8052, "zone": "A"},
    {"id": "BHOSARI", "name": "Bhosari", "lat": 18.6361, "lon": 73.8439, "zone": "A"},
    {"id": "KASARWADI", "name": "Kasarwadi", "lat": 18.6257, "lon": 73.8227, "zone": "A"},
    {"id": "PIMPRI", "name": "Pimpri", "lat": 18.6298, "lon": 73.7997, "zone": "A"},
    {"id": "CHINCHWAD", "name": "Chinchwad", "lat": 18.6452, "lon": 73.7997, "zone": "A"},
    {"id": "AKURDI", "name": "Akurdi", "lat": 18.6479, "lon": 73.7756, "zone": "B"},
    {"id": "NIGDI", "name": "Nigdi", "lat": 18.6612, "lon": 73.7667, "zone": "B"},
    {"id": "SWARGATE", "name": "Swargate", "lat": 18.5026, "lon": 73.8540, "zone": "C"},
    {"id": "MARKET_YARD", "name": "Market Yard", "lat": 18.5119, "lon": 73.8582, "zone": "C"},
    {"id": "SHIVAJINAGAR", "name": "Shivajinagar", "lat": 18.5308, "lon": 73.8474, "zone": "C"},
    {"id": "CIVIL_COURT", "name": "Civil Court", "lat": 18.5167, "lon": 73.8553, "zone": "C"},
    {"id": "PUNE_STATION", "name": "Pune Railway Station", "lat": 18.5295, "lon": 73.8740, "zone": "D"},
    {"id": "RUBY_HALL", "name": "Ruby Hall Clinic", "lat": 18.5362, "lon": 73.8879, "zone": "D"},
    {"id": "RANGE_HILLS", "name": "Range Hills", "lat": 18.5556, "lon": 73.8485, "zone": "D"},
]

DRIVER_NAMES = [
    "Ravi Kumar", "Suresh Patil", "Amit Sharma", "Rahul Jadhav", "Vijay Shinde",
    "Prakash Desai", "Nilesh More", "Ganesh Pawar", "Sachin Kulkarni", "Ajay Kadam",
    "Deepak Bhosale", "Rajesh Waghmare", "Santosh Mane", "Anil Gaikwad", "Manoj Salve",
    "Prashant Dhole", "Sandip Kale", "Tushar Bhor", "Vishwas Thorat", "Hemant Nale",
]
VEHICLE_TYPES = ["auto", "cab", "ebike"]


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def setup_db():
    # Create DB if not exists (connect to postgres first)
    try:
        conn = psycopg2.connect(
            dbname="postgres", user=DB_CONFIG["user"],
            password=DB_CONFIG["password"], host=DB_CONFIG["host"], port=DB_CONFIG["port"]
        )
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = 'transit_sync'")
        if not cur.fetchone():
            cur.execute("CREATE DATABASE transit_sync")
            print("✅ Created database transit_sync")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"DB creation note: {e}")

    conn = get_conn()
    conn.autocommit = True
    cur = conn.cursor()

    # Enable PostGIS
    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis_topology;")
    print("✅ PostGIS enabled")

    # Drop tables to ensure fresh schema
    cur.execute("DROP TABLE IF EXISTS ride_requests;")
    cur.execute("DROP TABLE IF EXISTS hotspots_predicted;")
    cur.execute("DROP TABLE IF EXISTS gtfs_trains;")
    cur.execute("DROP TABLE IF EXISTS drivers_live;")
    cur.execute("DROP TABLE IF EXISTS stations;")
    cur.execute("DROP TABLE IF EXISTS charging_hubs;")
    print("✅ Tables dropped (fresh start)")

    # Create tables
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stations (
            id VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            location GEOGRAPHY(Point, 4326),
            lat FLOAT,
            lon FLOAT,
            city VARCHAR DEFAULT 'Pune',
            zone VARCHAR,
            avg_daily_passengers INTEGER DEFAULT 5000
        );
        CREATE INDEX IF NOT EXISTS idx_stations_location ON stations USING GIST(location);
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS drivers_live (
            id VARCHAR PRIMARY KEY,
            name VARCHAR,
            vehicle_type VARCHAR,
            location GEOGRAPHY(Point, 4326),
            lat FLOAT,
            lon FLOAT,
            is_online BOOLEAN DEFAULT TRUE,
            is_available BOOLEAN DEFAULT TRUE,
            rating FLOAT DEFAULT 4.5,
            idle_since TIMESTAMP DEFAULT NOW(),
            assigned_hotspot VARCHAR,
            battery_level FLOAT DEFAULT 1.0,
            is_charging BOOLEAN DEFAULT FALSE,
            updated_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_drivers_location ON drivers_live USING GIST(location);
        CREATE INDEX IF NOT EXISTS idx_drivers_available ON drivers_live(is_available, is_online);
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS charging_hubs (
            id SERIAL PRIMARY KEY,
            name VARCHAR NOT NULL,
            location GEOGRAPHY(Point, 4326),
            lat FLOAT,
            lon FLOAT,
            capacity INTEGER DEFAULT 10,
            available_spots INTEGER DEFAULT 10,
            is_active BOOLEAN DEFAULT TRUE
        );
        CREATE INDEX IF NOT EXISTS idx_hubs_location ON charging_hubs USING GIST(location);
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS hotspots_predicted (
            id SERIAL PRIMARY KEY,
            station_id VARCHAR,
            location GEOGRAPHY(Point, 4326),
            lat FLOAT,
            lon FLOAT,
            predicted_passengers INTEGER,
            time_window_start TIMESTAMP,
            time_window_end TIMESTAMP,
            confidence FLOAT DEFAULT 0.8,
            weather VARCHAR DEFAULT 'clear',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_hotspots_location ON hotspots_predicted USING GIST(location);
        CREATE INDEX IF NOT EXISTS idx_hotspots_active ON hotspots_predicted(is_active, station_id);
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ride_requests (
            id VARCHAR PRIMARY KEY,
            passenger_name VARCHAR,
            pickup_location GEOGRAPHY(Point, 4326),
            pickup_lat FLOAT,
            pickup_lon FLOAT,
            destination_lat FLOAT,
            destination_lon FLOAT,
            status VARCHAR DEFAULT 'pending',
            driver_id VARCHAR,
            station_id VARCHAR,
            created_at TIMESTAMP DEFAULT NOW(),
            matched_at TIMESTAMP,
            wait_time_seconds INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_rides_status ON ride_requests(status);
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS gtfs_trains (
            trip_id VARCHAR PRIMARY KEY,
            route_id VARCHAR,
            station_id VARCHAR,
            scheduled_arrival TIMESTAMP,
            estimated_arrival TIMESTAMP,
            delay_minutes FLOAT DEFAULT 0,
            passenger_load INTEGER DEFAULT 0,
            status VARCHAR DEFAULT 'on_time'
        );
        CREATE INDEX IF NOT EXISTS idx_trains_station ON gtfs_trains(station_id);
        CREATE INDEX IF NOT EXISTS idx_trains_arrival ON gtfs_trains(estimated_arrival);
    """)

    print("✅ Tables and indexes created")

    # Seed stations
    cur.execute("DELETE FROM stations;")
    for s in STATIONS:
        cur.execute("""
            INSERT INTO stations (id, name, location, lat, lon, zone, avg_daily_passengers)
            VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s)
        """, (s["id"], s["name"], s["lon"], s["lat"], s["lat"], s["lon"],
              s["zone"], random.randint(3000, 12000)))
    print(f"✅ Seeded {len(STATIONS)} stations")

    # Seed Charging Hubs
    cur.execute("DELETE FROM charging_hubs;")
    HUBS = [
        {"name": "Pune Station Hub", "lat": 18.5280, "lon": 73.8735},
        {"name": "Shivajinagar Hub", "lat": 18.5315, "lon": 73.8480},
        {"name": "Swargate Hub", "lat": 18.5020, "lon": 73.8530},
        {"name": "PCMC Hub", "lat": 18.6270, "lon": 73.8000},
    ]
    for h in HUBS:
        cur.execute("""
            INSERT INTO charging_hubs (name, location, lat, lon, capacity, available_spots)
            VALUES (%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, 10, 10)
        """, (h["name"], h["lon"], h["lat"], h["lat"], h["lon"]))
    print(f"✅ Seeded {len(HUBS)} charging hubs")

    # Seed drivers around Pune
    cur.execute("DELETE FROM drivers_live;")
    base_lat, base_lon = 18.5726, 73.8546  # Pune center
    for i, name in enumerate(DRIVER_NAMES):
        vehicle = VEHICLE_TYPES[i % 3]
        lat = base_lat + random.uniform(-0.08, 0.08)
        lon = base_lon + random.uniform(-0.08, 0.08)
        driver_id = f"DRV_{i+1:03d}"
        
        # Twist 2: Random initial battery levels
        battery = round(random.uniform(0.3, 1.0), 2)
        if i % 5 == 0: battery = 0.18 # Some low battery drivers for testing
        
        cur.execute("""
            INSERT INTO drivers_live (
                id, name, vehicle_type, lat, lon, location, 
                is_online, is_available, rating, idle_since, battery_level
            )
            VALUES (
                %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                %s, %s, %s, %s, %s
            )
        """, (
            driver_id, name, vehicle, lat, lon, lon, lat,
            True, True, round(random.uniform(3.8, 5.0), 1),
            datetime.utcnow() - timedelta(minutes=random.randint(1, 60)), battery
        ))
    print(f"✅ Seeded {len(DRIVER_NAMES)} drivers with battery levels")

    # Seed GTFS trains
    cur.execute("DELETE FROM gtfs_trains;")
    now = datetime.utcnow()
    for i, station in enumerate(STATIONS):
        for j in range(3):  # 3 upcoming trains per station
            trip_id = f"TRIP_{station['id']}_{j}"
            scheduled = now + timedelta(minutes=(j * 20 + random.randint(5, 15)))
            delay = random.uniform(0, 8)
            estimated = scheduled + timedelta(minutes=delay)
            cur.execute("""
                INSERT INTO gtfs_trains (trip_id, route_id, station_id, scheduled_arrival, estimated_arrival, delay_minutes, passenger_load, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (trip_id, "PUNE_METRO_L1", station["id"], scheduled, estimated,
                  round(delay, 1), random.randint(50, 300),
                  "delayed" if delay > 3 else "on_time"))
    print(f"✅ Seeded GTFS train data")

    cur.close()
    conn.close()
    print("\n🎉 Database initialization complete!")


if __name__ == "__main__":
    setup_db()
