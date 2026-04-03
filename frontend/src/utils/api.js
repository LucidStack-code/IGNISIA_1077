// In development (Vite), we use relative paths to leverage the built-in proxy.
// In production, these should point to the actual production API/WS URLs.
const BASE = ''; 
const WS_SCHEME = window.location.protocol === 'https:' ? 'wss' : 'ws';
const WS_BASE = `${WS_SCHEME}://${window.location.host}`;

async function api(path, opts = {}) {
  // We prepend /api because Vite's proxy expects it
  const url = `${BASE}/api${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  });
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
  return res.json();
}

// ── Admin ────────────────────────────────────────────────────────────────────
export const getAdminDashboard  = ()             => api('/admin/dashboard');
export const getRideStats       = ()             => api('/rides/stats');
export const getGtfsSummary     = ()             => api('/gtfs/summary');

// ── Drivers ──────────────────────────────────────────────────────────────────
export const getDrivers         = ()             => api('/drivers');
export const getNearbyDrivers   = (lat, lon, r=3) => api(`/drivers/nearby?lat=${lat}&lon=${lon}&radius=${r}`);
export const optimizeFleet      = (radius = 5, surge = false) =>
  api('/fleet/optimize', { method: 'POST', body: JSON.stringify({ radius_km: radius, surge_mode: surge }) });
export const toggleDriver       = (driverId, online) => 
  api(`/drivers/${driverId}/status`, { method: 'PATCH', body: JSON.stringify({ is_online: online }) });

// ── Hotspots & Predictions ───────────────────────────────────────────────────
export const getHotspots        = ()             => api('/hotspots');
export const predictAllStations = ()             => api('/predict/all');
export const triggerHotspot     = (stationId, radius = 10, delay = 0) =>
  api('/hotspots/trigger', { method: 'POST', body: JSON.stringify({ station_id: stationId, radius_km: radius, delay_minutes: delay }) });

// ── Trains ───────────────────────────────────────────────────────────────────
export const getTrains          = ()             => api('/trains');
export const getStations        = ()             => api('/stations');
export const simulateArrival    = (stationId, delay = 0, passengers = 200) =>
  api('/trains/simulate', { method: 'POST', body: JSON.stringify({ station_id: stationId, delay_minutes: delay, passenger_load: passengers }) });

// ── Customer ─────────────────────────────────────────────────────────────────
export const requestRide        = (name, lat, lon, stationId) => 
  api('/rides/request', { 
    method: 'POST', 
    body: JSON.stringify({ 
      passenger_name: name, 
      pickup_lat: lat, 
      pickup_lon: lon, 
      station_id: stationId 
    }) 
  });
export const getRideStatus      = (rideId)       => api(`/rides/${rideId}`);
export const predictStation     = (stationId)    => api(`/predict/${stationId}`);

// ── Driver ───────────────────────────────────────────────────────────────────
export const updateDriverStatus = (driverId, payload) =>
  api(`/drivers/${driverId}/status`, { method: 'PATCH', body: JSON.stringify(payload) });
export const updateDriverLocation = (driverId, lat, lon) =>
  api(`/drivers/${driverId}/location`, { method: 'PATCH', body: JSON.stringify({ lat, lon }) });
export const completeRide       = (rideId)       => api(`/rides/${rideId}/complete`, { method: 'POST' });

// ── WebSockets ───────────────────────────────────────────────────────────────
export const createAdminWebSocket  = () => new WebSocket(`${WS_BASE}/ws/admin`);
export const createDriverWebSocket = (driverId) => new WebSocket(`${WS_BASE}/ws/driver/${driverId}`);
export const createPassengerWebSocket = (requestId) => new WebSocket(`${WS_BASE}/ws/passenger/${requestId}`);
export const createCustomerWebSocket = createPassengerWebSocket; // Legacy alias
