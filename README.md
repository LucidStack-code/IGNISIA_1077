# 🚇 TransitSync — Predictive Last-Mile Transit Synchronizer

> **Hackathon Project SC01** — Pre-positions vehicles before trains arrive using Hybrid ML (XGBoost + LSTM), PostGIS geofencing, WebSocket alerts, and real-time matching.

---

## 📁 Project Structure

```
transit-sync/
├── backend/
│   ├── main.py                    # FastAPI app + all API routes + WebSocket endpoints
│   ├── requirements.txt
│   ├── .env
│   ├── db/
│   │   ├── models.py              # SQLAlchemy models (PostGIS Geography columns)
│   │   └── init_db.py             # DB init + seed data (15 stations, 20 drivers, GTFS trains)
│   ├── ml/
│   │   └── demand_predictor.py    # Hybrid XGBoost + LSTM demand predictor
│   └── services/
│       ├── websocket_manager.py   # WS connection manager (driver/passenger/admin rooms)
│       ├── geofence_engine.py     # PostGIS ST_DWithin queries + driver ranking
│       ├── fleet_optimizer.py     # Greedy assignment + surge rebalancing + real-time match
│       └── gtfs_service.py        # GTFS feed parser + train simulation
├── frontend/
│   ├── src/
│   │   ├── App.js                 # Router with Nav
│   │   ├── index.css              # Global dark theme CSS
│   │   ├── utils/api.js           # All API/WS calls
│   │   └── pages/
│   │       ├── CustomerPage.jsx   # Ride request + live map + driver tracking
│   │       ├── DriverPage.jsx     # Hotspot alerts + navigation + earnings
│   │       └── AdminPage.jsx      # Heatmap + fleet table + analytics + simulation
│   └── public/index.html
├── docker-compose.yml             # PostgreSQL+PostGIS + Redis
├── start.sh                       # One-command startup
└── README.md
```

---

## ⚡ Quick Start (3 Steps)

### Prerequisites
- **Docker + Docker Compose** (for PostgreSQL/PostGIS)
- **Python 3.10+**
- **Node.js 18+**

---

### Step 1 — Start Database

```bash
cd transit-sync
docker-compose up -d
```

Wait ~10s for PostgreSQL to initialize, then verify:
```bash
docker logs transit_postgres | tail -5
# Should show: database system is ready to accept connections
```

---

### Step 2 — Start Backend

```bash
cd backend

# Create virtualenv and install deps
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Initialize DB with PostGIS + seed data
python3 db/init_db.py

# Start FastAPI server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

✅ Backend at: http://localhost:8000  
✅ API Docs: http://localhost:8000/docs  
✅ Health: http://localhost:8000/health  

---

### Step 3 — Start Frontend

Open a new terminal:
```bash
cd transit-sync/frontend
npm install --legacy-peer-deps
npm start
```

✅ Frontend at: http://localhost:3000

---

### Or use the one-command script:
```bash
chmod +x start.sh
./start.sh
```

---

## 🌐 Web Interfaces

| Interface | URL | Description |
|-----------|-----|-------------|
| 🧍 **Passenger** | http://localhost:3000/customer | Request rides, track driver in real-time |
| 🚗 **Driver** | http://localhost:3000/driver | Receive hotspot alerts, navigate, toggle availability |
| 📊 **Admin** | http://localhost:3000/admin | Heatmap, fleet table, analytics, simulation |

---

## 🔌 Key API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/gtfs/trains` | Live train ETAs |
| POST | `/api/gtfs/simulate` | Simulate train arrival at a station |
| POST | `/api/predict/demand` | ML demand prediction for a station |
| GET | `/api/predict/all-stations` | Predict demand at all stations |
| GET | `/api/drivers` | List all drivers with live positions |
| GET | `/api/drivers/nearby?lat=&lon=&radius_km=` | PostGIS geofence query |
| POST | `/api/drivers/location` | Update driver GPS position |
| POST | `/api/drivers/toggle` | Toggle driver online/offline |
| GET | `/api/hotspots` | Get active demand hotspots |
| POST | `/api/hotspots/trigger` | Trigger prediction + create hotspot |
| POST | `/api/fleet/optimize` | Run fleet pre-positioning algorithm |
| POST | `/api/rides/request` | Passenger requests a ride |
| GET | `/api/admin/dashboard` | Aggregated dashboard stats |
| WS | `/ws/driver/{id}` | Driver real-time channel |
| WS | `/ws/passenger/{id}` | Passenger tracking channel |
| WS | `/ws/admin` | Admin broadcast channel |

---

## 🤖 ML Architecture

```
Input Features:
  station_id (encoded), hour (cyclic sin/cos),
  day_of_week (cyclic), delay_minutes, weather (encoded),
  month, is_weekend

XGBoost Model (75% weight):
  - 200 estimators, max_depth=6
  - Trained on 3000 synthetic historical samples
  - Outputs: predicted passenger count

LSTM Mock (25% trend weight):
  - Exponential smoothing over last 48 time-steps
  - Captures recent demand trends
  - Outputs: trend multiplier (0.7–1.4)

Final = XGBoost_pred × (0.75 + 0.25 × LSTM_trend)
```

---

## 🗄️ Database Schema

```sql
-- PostGIS Geography columns with GIST indexes
stations          (id, name, location GEOGRAPHY(Point,4326), lat, lon, zone)
drivers_live      (id, name, vehicle_type, location GEOGRAPHY(Point,4326), lat, lon,
                   is_online, is_available, rating, idle_since, assigned_hotspot)
hotspots_predicted(id, station_id, location GEOGRAPHY(Point,4326), lat, lon,
                   predicted_passengers, time_window_start, time_window_end, confidence)
ride_requests     (id, passenger_name, pickup_location, status, driver_id, wait_time_seconds)
gtfs_trains       (trip_id, route_id, station_id, scheduled_arrival, estimated_arrival,
                   delay_minutes, passenger_load, status)
```

---

## 🎮 Demo Flow (Try This!)

1. **Open Admin Dashboard** → http://localhost:3000/admin
2. **Simulate a train arrival** → Select station, set 200 passengers, click "Simulate Arrival"
3. Watch the **Live Event Feed** — demand prediction fires, hotspot created, drivers notified
4. Click **"Optimize Fleet"** → Watch drivers get assigned to hotspot
5. Switch to **Driver page** → Go online, see hotspot alert, click "Navigate Here"
6. Switch to **Passenger page** → Click on map, enter name, request ride
7. Back to **Admin → Analytics** tab → See charts update in real-time

---

## 🚀 Hackathon Features Checklist

- [x] GTFS + GTFS-Realtime (mock) with ETAs
- [x] XGBoost demand prediction (trained on synthetic data)
- [x] LSTM pattern trend (mock implementation)
- [x] PostgreSQL + PostGIS with GEOGRAPHY columns + GIST indexes
- [x] PostGIS ST_DWithin geofence queries
- [x] WebSocket real-time notifications (driver/passenger/admin rooms)
- [x] Greedy fleet pre-positioning algorithm
- [x] Surge rebalancing (5km → 8km expansion)
- [x] Real-time ride matching (distance + wait_time + rating scoring)
- [x] 3 web interfaces (Customer, Driver, Admin)
- [x] Leaflet.js interactive maps
- [x] Demand heatmap visualization
- [x] Train simulation with demand prediction trigger
- [x] Fleet analytics with Recharts

---

## 🔧 Troubleshooting

**DB connection refused:**
```bash
docker-compose ps          # check containers running
docker-compose logs postgres
```

**XGBoost install fails:**
```bash
pip install xgboost --pre  # try pre-release
# OR: The system uses a rule-based fallback automatically
```

**Frontend can't reach backend:**
- Ensure backend is on port 8000
- Check CORS — backend allows `*` origins in dev mode
- Verify: `curl http://localhost:8000/health`

**Port already in use:**
```bash
lsof -i :8000 | awk 'NR>1{print $2}' | xargs kill  # free port 8000
lsof -i :3000 | awk 'NR>1{print $2}' | xargs kill  # free port 3000
```
