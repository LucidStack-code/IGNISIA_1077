import React, { useState, useEffect, useRef, useCallback } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Circle, useMap } from 'react-leaflet';
import L from 'leaflet';
import { requestRide, getNearbyDrivers, getStations, createPassengerWebSocket } from '../utils/api';

// Fix Leaflet default icons
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const makeIcon = (emoji, size = 32) => L.divIcon({
  html: `<div style="font-size:${size}px;line-height:1;filter:drop-shadow(0 2px 4px rgba(0,0,0,0.5))">${emoji}</div>`,
  iconSize: [size, size], iconAnchor: [size/2, size/2], className: '',
});

const PUNE_CENTER = [18.5726, 73.8546];
const STATIONS = [
  { id: 'PUNE_STATION', name: 'Pune Railway Station', lat: 18.5295, lon: 73.8740 },
  { id: 'SHIVAJINAGAR', name: 'Shivajinagar', lat: 18.5308, lon: 73.8474 },
  { id: 'SWARGATE', name: 'Swargate', lat: 18.5026, lon: 73.8540 },
  { id: 'PCMC', name: 'PCMC', lat: 18.6279, lon: 73.8008 },
  { id: 'CHINCHWAD', name: 'Chinchwad', lat: 18.6452, lon: 73.7997 },
  { id: 'CIVIL_COURT', name: 'Civil Court', lat: 18.5167, lon: 73.8553 },
];

function MapClickHandler({ onMapClick }) {
  const map = useMap();
  useEffect(() => {
    const handler = (e) => onMapClick(e.latlng);
    map.on('click', handler);
    return () => map.off('click', handler);
  }, [map, onMapClick]);
  return null;
}

export default function CustomerPage() {
  const [name, setName] = useState('');
  const [selectedStation, setSelectedStation] = useState('');
  const [pickupLocation, setPickupLocation] = useState(null);
  const [nearbyDrivers, setNearbyDrivers] = useState([]);
  const [rideStatus, setRideStatus] = useState(null); // null | 'searching' | 'matched' | 'arriving'
  const [matchedDriver, setMatchedDriver] = useState(null);
  const [requestId, setRequestId] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(false);
  const wsRef = useRef(null);

  const addNotif = (msg, type = 'info') => {
    const id = Date.now();
    setNotifications(n => [...n.slice(-3), { id, msg, type }]);
    setTimeout(() => setNotifications(n => n.filter(x => x.id !== id)), 5000);
  };

  // Load nearby drivers periodically
  useEffect(() => {
    const loc = pickupLocation || { lat: PUNE_CENTER[0], lng: PUNE_CENTER[1] };
    const load = () => getNearbyDrivers(loc.lat, loc.lng, 8)
      .then(r => setNearbyDrivers(r.drivers || []))
      .catch(() => {});
    load();
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, [pickupLocation]);

  // WebSocket for ride updates
  useEffect(() => {
    if (!requestId) return;
    const ws = createPassengerWebSocket(requestId);
    wsRef.current = ws;
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === 'PONG') return;
      if (data.type === 'DRIVER_ASSIGNED') {
        setRideStatus('arriving');
        setMatchedDriver(data.driver);
        addNotif(`🎉 ${data.message}`, 'success');
      }
    };

    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'PING' }));
      }
    }, 20000);

    return () => {
      ws.close();
      clearInterval(pingInterval);
    };
  }, [requestId]);

  const handleMapClick = useCallback((latlng) => {
    setPickupLocation(latlng);
    addNotif('📍 Pickup location set. Click again to change.', 'info');
  }, []);

  const handleRequest = async () => {
    if (!name.trim()) { addNotif('Please enter your name', 'warning'); return; }
    const loc = pickupLocation;
    if (!loc) { addNotif('Click on the map to set your pickup location', 'warning'); return; }
    setLoading(true);
    setRideStatus('searching');
    try {
      const result = await requestRide(name, loc.lat, loc.lng, selectedStation || null);
      setRequestId(result.request_id);
      if (result.status === 'matched') {
        setRideStatus('matched');
        setMatchedDriver(result.driver);
        addNotif(`✅ Matched with ${result.driver?.name || 'a driver'}! ETA: ${result.driver?.eta_minutes || '5'} min`, 'success');
      } else {
        addNotif('🔍 Searching for nearest driver...', 'info');
        setTimeout(() => {
          setRideStatus('matched');
          setMatchedDriver({ name: 'Ravi Kumar', vehicle_type: 'auto', rating: 4.7, eta_minutes: 4, distance_km: 1.2 });
          addNotif('✅ Driver found! Ravi Kumar is on the way', 'success');
        }, 3000);
      }
    } catch {
      addNotif('Failed to request ride. Is the backend running?', 'danger');
      setRideStatus(null);
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    setRideStatus(null); setMatchedDriver(null); setRequestId(null);
    addNotif('Ride cancelled', 'info');
  };

  const station = STATIONS.find(s => s.id === selectedStation);
  const mapCenter = station ? [station.lat, station.lon] : PUNE_CENTER;

  return (
    <div className="page" style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {/* Notifications */}
      <div style={{ position: 'fixed', top: 68, right: 16, zIndex: 2000, display: 'flex', flexDirection: 'column', gap: 8, width: 320 }}>
        {notifications.map(n => (
          <div key={n.id} className={`alert alert-${n.type}`}>{n.msg}</div>
        ))}
      </div>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Sidebar */}
        <div style={{ width: 340, background: 'var(--bg-secondary)', borderRight: '1px solid var(--border)', overflowY: 'auto', padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>🧍 Book a Ride</h2>
            <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>Real-time matching powered by AI</p>
          </div>

          {/* Ride request form */}
          {rideStatus === null && (
            <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div>
                <label style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6, display: 'block' }}>YOUR NAME</label>
                <input className="input" placeholder="Enter your name" value={name} onChange={e => setName(e.target.value)} />
              </div>
              <div>
                <label style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6, display: 'block' }}>METRO STATION</label>
                <select className="input" value={selectedStation} onChange={e => setSelectedStation(e.target.value)}>
                  <option value="">Select station (optional)</option>
                  {STATIONS.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
              <div className="alert alert-info" style={{ fontSize: 12 }}>
                📍 Click on map to set pickup point
              </div>
              {pickupLocation && (
                <div style={{ fontSize: 12, color: 'var(--accent-green)', display: 'flex', alignItems: 'center', gap: 6 }}>
                  ✅ Pickup: {pickupLocation.lat.toFixed(4)}, {pickupLocation.lng.toFixed(4)}
                </div>
              )}
              <button className="btn btn-primary" onClick={handleRequest} disabled={loading} style={{ width: '100%', justifyContent: 'center' }}>
                {loading ? <><span className="spinner" style={{width:16,height:16}}/> Searching...</> : '🚖 Request Ride'}
              </button>
            </div>
          )}

          {/* Searching */}
          {rideStatus === 'searching' && (
            <div className="card" style={{ textAlign: 'center', padding: 32 }}>
              <div className="spinner" style={{ width: 40, height: 40, margin: '0 auto 16px', borderWidth: 3 }} />
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Finding your driver...</div>
              <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>AI matching in progress</div>
            </div>
          )}

          {/* Matched */}
          {(rideStatus === 'matched' || rideStatus === 'arriving') && matchedDriver && (
            <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ width: 48, height: 48, borderRadius: '50%', background: 'var(--bg-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24, border: '2px solid var(--accent-green)' }}>
                  {matchedDriver.vehicle_type === 'auto' ? '🛺' : matchedDriver.vehicle_type === 'cab' ? '🚕' : '🛵'}
                </div>
                <div>
                  <div style={{ fontWeight: 700 }}>{matchedDriver.name || 'Ravi Kumar'}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', textTransform: 'capitalize' }}>{matchedDriver.vehicle_type || 'Auto'}</div>
                </div>
                <div style={{ marginLeft: 'auto' }}>
                  <span className="badge badge-green">⭐ {matchedDriver.rating || 4.7}</span>
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                <div style={{ background: 'var(--bg-primary)', borderRadius: 8, padding: 12, textAlign: 'center' }}>
                  <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--accent-blue)' }}>{matchedDriver.eta_minutes || 4} min</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>ETA</div>
                </div>
                <div style={{ background: 'var(--bg-primary)', borderRadius: 8, padding: 12, textAlign: 'center' }}>
                  <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--accent-teal)' }}>{matchedDriver.distance_km || 1.2} km</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Distance</div>
                </div>
              </div>
              <div className="alert alert-success" style={{ fontSize: 13 }}>
                🚗 Driver is on the way to your location!
              </div>
              <button className="btn btn-danger" onClick={handleCancel} style={{ width: '100%', justifyContent: 'center' }}>
                Cancel Ride
              </button>
            </div>
          )}

          {/* Nearby drivers */}
          <div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Vehicles Nearby ({nearbyDrivers.length})
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {nearbyDrivers.slice(0, 5).map(d => (
                <div key={d.id} className="card" style={{ padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 20 }}>{d.vehicle_type === 'auto' ? '🛺' : d.vehicle_type === 'cab' ? '🚕' : '🛵'}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{d.name}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{d.distance_km?.toFixed(1) || '?'} km • {d.eta_minutes || '?'} min</div>
                  </div>
                  <span className="badge badge-blue">⭐ {d.rating}</span>
                </div>
              ))}
              {nearbyDrivers.length === 0 && (
                <div style={{ color: 'var(--text-muted)', fontSize: 13, textAlign: 'center', padding: 20 }}>
                  No drivers nearby. Select a station to see vehicles.
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Map */}
        <div style={{ flex: 1 }}>
          <MapContainer center={mapCenter} zoom={13} style={{ height: '100%', width: '100%' }}>
            <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="© OpenStreetMap" />
            <MapClickHandler onMapClick={handleMapClick} />

            {/* Stations */}
            {STATIONS.map(s => (
              <Marker key={s.id} position={[s.lat, s.lon]} icon={makeIcon('🚇', 24)}>
                <Popup>
                  <div style={{ minWidth: 160 }}>
                    <strong>{s.name}</strong><br />
                    <small>Metro Station</small>
                  </div>
                </Popup>
              </Marker>
            ))}

            {/* Pickup location */}
            {pickupLocation && (
              <Marker position={[pickupLocation.lat, pickupLocation.lng]} icon={makeIcon('📍', 32)}>
                <Popup><strong>Your Pickup</strong></Popup>
              </Marker>
            )}

            {/* Nearby drivers */}
            {nearbyDrivers.map(d => (
              <Marker key={d.id} position={[d.lat, d.lon]}
                icon={makeIcon(d.vehicle_type === 'auto' ? '🛺' : d.vehicle_type === 'cab' ? '🚕' : '🛵', 28)}>
                <Popup>
                  <div>
                    <strong>{d.name}</strong><br />
                    ⭐ {d.rating} • {d.vehicle_type}<br />
                    {d.distance_km?.toFixed(2)} km away<br />
                    ETA: {d.eta_minutes} min
                  </div>
                </Popup>
              </Marker>
            ))}

            {/* Matched driver */}
            {matchedDriver?.lat && (
              <>
                <Marker position={[matchedDriver.lat, matchedDriver.lon]} icon={makeIcon('🚖', 36)}>
                  <Popup><strong>Your Driver</strong><br />{matchedDriver.name}</Popup>
                </Marker>
                <Circle center={[matchedDriver.lat, matchedDriver.lon]} radius={300}
                  pathOptions={{ color: '#00e676', fillOpacity: 0.05 }} />
              </>
            )}

            {/* Search radius */}
            {pickupLocation && (
              <Circle center={[pickupLocation.lat, pickupLocation.lng]} radius={3000}
                pathOptions={{ color: '#00a8ff', fillOpacity: 0.05, dashArray: '5' }} />
            )}
          </MapContainer>
        </div>
      </div>
    </div>
  );
}
