# TransitSync 🚀


**TransitSync** is an advanced, predictive last-mile synchronization platform designed to bridge the gap between high-capacity transit (Metro/Trains) and individual last-mile transport (E-bikes/Cabs). 

By leveraging real-time data and machine learning, the platform predicts demand surges, models network-wide disruptions, and manages a battery-constrained fleet to ensure passengers are never stranded.

---

## 🛑 The Problem
Transit networks are highly interconnected. A single train breakdown doesn't just stall one station; it creates a "ripple effect" of stranded passengers who spill over to neighboring stations, causing unpredictable demand surges that existing taxi/e-bike fleets cannot anticipate. 

## ✅ The Solution
TransitSync provides an integrated **Admin Dashboard** and **Predictive Engine** that:
1.  **Predicts Demand**: Uses a Hybrid ML model (XGBoost + LSTM) to forecast passenger loads 30–60 minutes ahead.
2.  **Models Ripples**: Simulates network "contagion" where disruptions at one station propagate demand to others.
3.  **Manages Resources**: Enforces real-world battery constraints, autonomously routing low-power vehicles to strategic **Charging Hubs**.

---

## ✨ Key Features

### 🌐 Advanced Network Simulation
- **Ripple Effect Engine**: Models passenger "spill-over" downstream from station disruptions with realistic time delays.
- **Disruption Simulator**: Allows admins to trigger "Breakdowns" and observe real-time demand propagation across the Pune Metro L1 layout.

### 🔋 Battery-Aware Fleet Management
- **Autonomous Charging**: Idle vehicles with <15% battery automatically self-route to the nearest charging hub.
- **Range Constraints**: Low-battery vehicles are restricted to short-radius trips to prevent stranding.
- **Live Health Monitoring**: Color-coded battery status (Green/Orange/Red) for every vehicle in the fleet.

### 📊 Admin Intelligence Dashboard
- **Predictive Heatmaps**: Visualizes demand "glow" based on future predictions at T+30 and T+60 minutes.
- **Proactive Optimization**: A one-click "Surge Mode" that pre-positions drivers based on future forecasted demand rather than current location.
- **Live GTFS Feed**: Real-time train tracking and arrival time (ETA) calculation.

---

## 🛠️ Tech Stack

-   **Frontend**: 
    -   React.js (Vite)
    -   Leaflet.js (Interactive Geospatial Mapping)
    -   Lucide React (Modern Iconography)
    -   Vanilla CSS3 (Responsive Design & Glassmorphism)
-   **Backend**: 
    -   FastAPI (Asynchronous Python Framework)
    -   XGBoost (Demand Prediction Model)
    -   PostgreSQL + PostGIS (Spatial Database)
    -   Redis (Real-time Pub/Sub & Caching)
    -   Uvicorn (ASGI Server)
-   **DevOps**: 
    -   Docker & Docker Compose (Containerization)
    -   Python Virtual Environments

---

## 🏗️ Architecture Overview

```mermaid
graph TD
    A[Admin Dashboard] <--> B[FastAPI Backend]
    B <--> C[(PostgreSQL/PostGIS)]
    B <--> D[Redis Pub/Sub]
    B --> E[Simulation Engine]
    E --> F[Ripple Effect Engine]
    E --> G[Battery Manager]
    B --> H[Hybrid ML Predictor]
    H --> I[XGBoost Model]
    H --> J[LSTM Trend Mock]
```

---

## 🚀 Installation & Setup

### 1. Prerequisites
- Docker & Docker Compose
- Python 3.10+
- Node.js 18+

### 2. Environment Configuration
Create a `.env` file in the `backend/` directory:
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/transit_sync
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your_secret_key
```

### 3. Database Initialization
Run the database setup script to create tables and seed initial data:
```bash
cd backend
python db/init_db.py
```

### 4. Running the Project
Use Docker Compose to start the database and Redis services:
```bash
docker-compose up -d
```

Start the **Backend**:
```bash
cd backend
venv\Scripts\activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Start the **Frontend**:
```bash
cd frontend
npm install
npm run dev
```

---

## 🎮 Demo Instructions

### 1. Trigger a Disruption
Simulate a breakdown at Pune Railway Station to see the ripple effect in action:
```powershell
Invoke-RestMethod -Uri http://localhost:8000/api/simulate/disruption -Method POST -ContentType "application/json" -Body '{"station_id": "PUNE_STATION", "intensity": 0.5}'
```

### 2. Register a New Driver
```powershell
Invoke-RestMethod -Uri http://localhost:8000/api/drivers -Method POST -ContentType "application/json" -Body '{"name":"Tester Joe", "vehicle_type":"cab", "lat":18.52, "lon":73.85}'
```

### 3. Book a Ride
```powershell
Invoke-RestMethod -Uri http://localhost:8000/api/rides/request -Method POST -ContentType "application/json" -Body '{"passenger_name":"John Doe", "pickup_lat":18.53, "pickup_lon":73.86}'
```

---

## 🔮 Future Scope
-   **Routing Engine Integration**: Integration with OSRM or Google Maps API for real-time traffic-aware navigation.
-   **Driver Mobile App**: Dedicated interface for drivers to receive repositioning requests and manage charging.
-   **Advanced ML Training**: Moving from static weights to a globally trained LSTM model using real historical transit data.
-   **Dynamic Pricing**: Surge pricing implementation based on ripple intensity.

---
Made with ❤️ by the **TechWizard Team** (LucidStack-code).
