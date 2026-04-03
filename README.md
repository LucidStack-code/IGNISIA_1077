# TransitMind AI — Indian Last-Mile Transit Platform

FastAPI + React hackathon project simulating rail arrivals, passenger demand surges, and realtime last-mile vehicle allocation for Pune stations.

## Setup

a. Clone repo

b. Create Neon DB and paste `DATABASE_URL` in `.env` (copy from `.env.example`)

c. Install backend deps:

```bash
pip install -r backend/requirements.txt
```

d. Seed data:

```bash
python seed.py
```

e. Run backend:

```bash
uvicorn backend.main:app --reload
```

f. Run frontend:

```bash
cd frontend
npm install
npm run dev
```

g. Open http://localhost:5173/admin

h. Click "▶ Trigger Demo: Deccan Express Delay"

i. Watch SURGE trigger at Pune Junction

## Endpoints

- REST:
  - `GET /api/stations/`
  - `GET /api/vehicles/`
  - `GET /api/trains/`
  - `GET /api/metrics/`
- WS:
  - `ws://localhost:8000/ws`

## Notes

- 1 second tick = 1 simulation minute.
- Uses OpenStreetMap + Leaflet only.
- Theme toggle persists in localStorage.
