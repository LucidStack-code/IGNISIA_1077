#!/bin/bash
# TransitSync - One-command startup script
# Usage: ./start.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

banner() {
  echo -e "${CYAN}"
  echo "  ╔════════════════════════════════════════════╗"
  echo "  ║   🚇 TransitSync — Last-Mile Platform      ║"
  echo "  ║   Predictive Fleet Positioning System      ║"
  echo "  ╚════════════════════════════════════════════╝"
  echo -e "${NC}"
}

log()  { echo -e "${GREEN}✅ $1${NC}"; }
info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
err()  { echo -e "${RED}❌ $1${NC}"; }

banner

# ── Step 1: Docker services ──────────────────────────────────────────────────
info "Starting PostgreSQL + PostGIS + Redis via Docker..."
if command -v docker &>/dev/null && command -v docker-compose &>/dev/null; then
  docker-compose up -d
  info "Waiting for PostgreSQL to be ready..."
  for i in $(seq 1 20); do
    if docker exec transit_postgres pg_isready -U postgres &>/dev/null 2>&1; then
      log "PostgreSQL is ready!"
      break
    fi
    sleep 2
    echo -n "."
  done
  echo ""
else
  warn "Docker not found. Assuming PostgreSQL is already running on localhost:5432"
fi

# ── Step 2: Python backend ───────────────────────────────────────────────────
info "Setting up Python backend..."
cd backend

if [ ! -d "venv" ]; then
  python3 -m venv venv
  log "Created Python virtual environment"
fi

source venv/bin/activate
pip install -q -r requirements.txt
log "Python dependencies installed"

# Initialize database
python3 db/init_db.py
log "Database initialized with seed data"

# Start backend in background
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
log "FastAPI backend started (PID $BACKEND_PID) → http://localhost:8000"
log "API Docs: http://localhost:8000/docs"

cd ..

# ── Step 3: React frontend ───────────────────────────────────────────────────
info "Setting up React frontend..."
cd frontend

if [ ! -d "node_modules" ]; then
  npm install --legacy-peer-deps
  log "Node dependencies installed"
fi

# Start frontend
REACT_APP_API_URL=http://localhost:8000 \
REACT_APP_WS_URL=ws://localhost:8000 \
npm start &
FRONTEND_PID=$!
log "React frontend starting (PID $FRONTEND_PID) → http://localhost:3000"

cd ..

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  🎉 TransitSync is starting up!${NC}"
echo ""
echo -e "  ${CYAN}🌐 Passenger Page:  ${NC}http://localhost:3000/customer"
echo -e "  ${CYAN}🚗 Driver Page:     ${NC}http://localhost:3000/driver"
echo -e "  ${CYAN}📊 Admin Dashboard: ${NC}http://localhost:3000/admin"
echo -e "  ${CYAN}🔌 API Docs:        ${NC}http://localhost:8000/docs"
echo -e "  ${CYAN}❤️  Health Check:   ${NC}http://localhost:8000/health"
echo ""
echo -e "  Press ${RED}Ctrl+C${NC} to stop all services"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Keep alive, cleanup on exit
trap "echo ''; info 'Shutting down...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; docker-compose down 2>/dev/null; exit 0" SIGINT SIGTERM

wait
