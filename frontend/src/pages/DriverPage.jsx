import React, { useState, useEffect, useRef, useCallback } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Circle, Polyline } from 'react-leaflet';
import L from 'leaflet';
import { getHotspots, toggleDriver, updateDriverLocation, createDriverWebSocket, getTrains } from '../utils/api';

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const makeIcon = (emoji, size = 32) => L.divIcon({
  html: `<div style="font-size:${size}px;line-height:1;filter:drop-shadow(0 2px 4px rgba(0,0,0,0.5))">${emoji}</div>`,
  iconSize: [size, size], iconAnchor: [size / 2, size / 2], className: '',
});

const PUNE_CENTER = [18.5726, 73.8546];
const DRIVER_NAMES = ['Ravi Kumar', 'Suresh Patil', 'Amit Sharma', 'Rahul Jadhav', 'Vijay Shinde'];
const VEHICLE_TYPES = ['auto', 'cab', 'ebike'];

export default function DriverPage() {
  const [driverId] = useState(() => `DRV_${Math.floor(Math.random() * 900 + 100)}`);
  const [driverName] = useState(DRIVER_NAMES[Math.floor(Math.random() * DRIVER_NAMES.length)]);
  const [vehicleType] = useState(VEHICLE_TYPES[Math.floor(Math.random() * 3)]);
  const [isOnline, setIsOnline] = useState(false);
  const [position, setPosition] = useState({ lat: PUNE_CENTER[0] + (Math.random() - 0.5) * 0.05, lng: PUNE_CENTER[1] + (Math.random() - 0.5) * 0.05 });
  const [hotspots, setHotspots] = useState([]);
  const [trains, setTrains] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [activeHotspot, setActiveHotspot] = useState(null);
  const [earnings, setEarnings] = useState({ today: 847, trips: 12, rating: 4.8 });
  const [wsStatus, setWsStatus] = useState('disconnected');
  const wsRef = useRef(null);

  const addAlert = (msg, type = 'info') => {
    const id = Date.now();
    setAlerts(a => [...a.slice(-4), { id, msg, type }]);
  };
  const dismissAlert = (id) => setAlerts(a => a.filter(x => x.id !== id));

  // Load data
  useEffect(() => {
    const load = () => {
      getHotspots().then(r => setHotspots(r.hotspots || [])).catch(() => {
        setHotspots([
          { id: 1, station_id: 'PUNE_STATION', station_name: 'Pune Railway Station', lat: 18.5295, lon: 73.8740, predicted_passengers: 185, confidence: 0.88 },
          { id: 2, station_id: 'SHIVAJINAGAR', station_name: 'Shivajinagar', lat: 18.5308, lon: 73.8474, predicted_passengers: 120, confidence: 0.81 },
          { id: 3, station_id: 'SWARGATE', station_name: 'Swargate', lat: 18.5026, lon: 73.8540, predicted_passengers: 95, confidence: 0.76 },
        ]);
      });
      getTrains().then(r => setTrains((r.trains || []).slice(0, 5))).catch(() => {
        setTrains([
          { trip_id: 'T1', station_name: 'Pune Railway Station', minutes_until_arrival: 7, delay_minutes: 0, passenger_load: 220, status: 'on_time' },
          { trip_id: 'T2', station_name: 'Shivajinagar', minutes_until_arrival: 12, delay_minutes: 2.5, passenger_load: 145, status: 'delayed' },
        ]);
      });
    };
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, []);

  // WebSocket
  useEffect(() => {
    if (!isOnline) return;
    const ws = createDriverWebSocket(driverId);
    wsRef.current = ws;
    ws.onopen = () => { setWsStatus('connected'); addAlert('🔌 Connected to dispatch server', 'success'); };
    ws.onclose = () => setWsStatus('disconnected');
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type === 'HOTSPOT_ALERT' || data.type === 'REPOSITIONING_REQUEST') {
          addAlert(`🚨 ${data.message || 'New hotspot demand detected!'}`, 'warning');
        } else if (data.type === 'RIDE_MATCHED') {
          addAlert(`🎯 New ride matched! Passenger waiting.`, 'success');
          setEarnings(e => ({ ...e, trips: e.trips + 1, today: e.today + Math.floor(Math.random() * 80 + 60) }));
        }
      } catch {}
    };
    return () => ws.close();
  }, [isOnline, driverId]);

  const toggleOnline = async () => {
    const newStatus = !isOnline;
    setIsOnline(newStatus);
    try {
      await toggleDriver(driverId, newStatus);
    } catch {}
    if (newStatus) {
      addAlert(`🟢 You're now online and visible to passengers`, 'success');
    } else {
      addAlert('🔴 You went offline', 'info');
      if (wsRef.current) wsRef.current.close();
    }
  };

  const moveToHotspot = (hotspot) => {
    setActiveHotspot(hotspot);
    addAlert(`🗺️ Navigating to ${hotspot.station_name}. ${hotspot.predicted_passengers} passengers expected.`, 'info');
    // Simulate movement
    let steps = 0;
    const target = { lat: hotspot.lat, lng: hotspot.lon };
    const interval = setInterval(() => {
      steps++;
      setPosition(prev => ({
        lat: prev.lat + (target.lat - prev.lat) * 0.15,
        lng: prev.lng + (target.lng - prev.lng) * 0.15,
      }));
      if (steps >= 12) {
        clearInterval(interval);
        setPosition({ lat: hotspot.lat + 0.002, lng: hotspot.lon + 0.001 });
        addAlert(`✅ Arrived at ${hotspot.station_name}!`, 'success');
        setEarnings(e => ({ ...e, trips: e.trips + 1, today: e.today + 120 }));
      }
    }, 800);
  };

  const vehicleEmoji = vehicleType === 'auto' ? '🛺' : vehicleType === 'cab' ? '🚕' : '🛵';

  return (
    <div className="page" style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Alerts overlay */}
      <div style={{ position: 'fixed', top: 68, right: 16, zIndex: 2000, display: 'flex', flexDirection: 'column', gap: 8, width: 340 }}>
        {alerts.map(a => (
          <div key={a.id} className={`alert alert-${a.type}`} style={{ cursor: 'pointer', justifyContent: 'space-between' }} onClick={() => dismissAlert(a.id)}>
            <span>{a.msg}</span>
            <span style={{ opacity: 0.6, fontSize: 12 }}>×</span>
          </div>
        ))}
      </div>

      {/* Left sidebar */}
      <div style={{ width: 340, background: 'var(--bg-secondary)', borderRight: '1px solid var(--border)', overflowY: 'auto', padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>

        {/* Driver profile */}
        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 52, height: 52, borderRadius: '50%', background: 'var(--bg-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28, border: `2px solid ${isOnline ? 'var(--accent-green)' : 'var(--border)'}` }}>
            {vehicleEmoji}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700 }}>{driverName}</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{driverId} • {vehicleType}</div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: isOnline ? 'var(--accent-green)' : 'var(--text-muted)', boxShadow: isOnline ? '0 0 8px var(--accent-green)' : 'none' }} />
            <span className="badge" style={{ background: 'rgba(0,0,0,0.3)', color: wsStatus === 'connected' ? 'var(--accent-green)' : 'var(--text-muted)', border: 'none', fontSize: 10 }}>
              WS {wsStatus}
            </span>
          </div>
        </div>

        {/* Toggle online */}
        <button className={`btn ${isOnline ? 'btn-danger' : 'btn-success'}`} onClick={toggleOnline} style={{ width: '100%', justifyContent: 'center', padding: 14, fontSize: 15 }}>
          {isOnline ? '🔴 Go Offline' : '🟢 Go Online'}
        </button>

        {/* Earnings */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
          {[
            { label: 'Today', value: `₹${earnings.today}`, color: 'var(--accent-green)' },
            { label: 'Trips', value: earnings.trips, color: 'var(--accent-blue)' },
            { label: 'Rating', value: `⭐${earnings.rating}`, color: 'var(--accent-orange)' },
          ].map(s => (
            <div key={s.label} style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 10, padding: '10px 8px', textAlign: 'center' }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: s.color }}>{s.value}</div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{s.label}</div>
            </div>
          ))}
        </div>

        {/* Upcoming trains */}
        <div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>🚆 Upcoming Trains</div>
          {trains.slice(0, 3).map(t => (
            <div key={t.trip_id} className="card" style={{ padding: '10px 14px', marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600 }}>{t.station_name}</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{t.passenger_load || '?'} pax load</div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: 16, fontWeight: 700, color: t.delay_minutes > 0 ? 'var(--accent-orange)' : 'var(--accent-green)' }}>
                  {t.minutes_until_arrival} min
                </div>
                <span className={`badge ${t.status === 'delayed' ? 'badge-orange' : 'badge-green'}`} style={{ fontSize: 9 }}>
                  {t.status}
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* Demand hotspots */}
        <div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
            🔥 Demand Hotspots ({hotspots.length})
          </div>
          {hotspots.map(h => (
            <div key={h.id} className="card" style={{ marginBottom: 8, padding: '12px 14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700 }}>{h.station_name || h.station_id}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    {(Math.hypot(h.lat - position.lat, h.lon - position.lng) * 111).toFixed(1)} km away
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--accent-red)' }}>
                    {h.predicted_passengers}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>passengers</div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
                <div style={{ flex: 1, background: 'var(--bg-primary)', borderRadius: 4, height: 4, overflow: 'hidden' }}>
                  <div style={{ width: `${(h.confidence || 0.8) * 100}%`, height: '100%', background: 'var(--accent-blue)', borderRadius: 4 }} />
                </div>
                <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{Math.round((h.confidence || 0.8) * 100)}% conf</span>
              </div>
              <button className="btn btn-primary" style={{ width: '100%', justifyContent: 'center', padding: '8px', fontSize: 13 }}
                onClick={() => moveToHotspot(h)} disabled={!isOnline}>
                🗺️ Navigate Here
              </button>
            </div>
          ))}
          {hotspots.length === 0 && (
            <div style={{ color: 'var(--text-muted)', fontSize: 13, textAlign: 'center', padding: 20 }}>
              No active hotspots. Go online to receive alerts.
            </div>
          )}
        </div>
      </div>

      {/* Map */}
      <div style={{ flex: 1 }}>
        <MapContainer center={[position.lat, position.lng]} zoom={13} style={{ height: '100%', width: '100%' }}>
          <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="© OpenStreetMap" />

          {/* My position */}
          <Marker position={[position.lat, position.lng]} icon={makeIcon(vehicleEmoji, 36)}>
            <Popup>
              <div><strong>📍 You ({driverName})</strong><br />
                Status: {isOnline ? '🟢 Online' : '🔴 Offline'}</div>
            </Popup>
          </Marker>

          {/* Hotspots */}
          {hotspots.map(h => (
            <React.Fragment key={h.id}>
              <Circle center={[h.lat, h.lon]}
                radius={400 + h.predicted_passengers * 5}
                pathOptions={{ color: '#ff1744', fillOpacity: 0.1 + (h.predicted_passengers / 500) * 0.15 }} />
              <Marker position={[h.lat, h.lon]} icon={makeIcon('🔥', 28)}>
                <Popup>
                  <div>
                    <strong>{h.station_name}</strong><br />
                    👥 {h.predicted_passengers} passengers expected<br />
                    📊 {Math.round((h.confidence || 0.8) * 100)}% confidence<br />
                    <button onClick={() => moveToHotspot(h)} style={{ marginTop: 8, padding: '4px 12px', background: '#00a8ff', color: 'white', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 12 }}>
                      Navigate
                    </button>
                  </div>
                </Popup>
              </Marker>
            </React.Fragment>
          ))}

          {/* Navigation line */}
          {activeHotspot && (
            <Polyline positions={[[position.lat, position.lng], [activeHotspot.lat, activeHotspot.lon]]}
              pathOptions={{ color: '#00a8ff', dashArray: '8 4', weight: 2 }} />
          )}
        </MapContainer>
      </div>
    </div>
  );
}
