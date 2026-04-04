import React, { useState, useEffect, useRef, useCallback } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Circle, useMap } from 'react-leaflet';
import L from 'leaflet';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell } from 'recharts';
import {
  getAdminDashboard, getDrivers, getHotspots, predictAllStations,
  getTrains, optimizeFleet, simulateArrival, triggerDisruption,
  createAdminWebSocket, getRideStats, getGtfsSummary, getHubs
} from '../utils/api';

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const makeIcon = (emoji, size = 28) => L.divIcon({
  html: `<div style="font-size:${size}px;line-height:1;filter:drop-shadow(0 2px 4px rgba(0,0,0,0.6))">${emoji}</div>`,
  iconSize: [size, size], iconAnchor: [size / 2, size / 2], className: '',
});

const STATIONS = [
  { id: 'PUNE_STATION', name: 'Pune Railway Station', lat: 18.5295, lon: 73.8740 },
  { id: 'SHIVAJINAGAR', name: 'Shivajinagar', lat: 18.5308, lon: 73.8474 },
  { id: 'SWARGATE', name: 'Swargate', lat: 18.5026, lon: 73.8540 },
  { id: 'PCMC', name: 'PCMC', lat: 18.6279, lon: 73.8008 },
  { id: 'CHINCHWAD', name: 'Chinchwad', lat: 18.6452, lon: 73.7997 },
  { id: 'CIVIL_COURT', name: 'Civil Court', lat: 18.5167, lon: 73.8553 },
  { id: 'AKURDI', name: 'Akurdi', lat: 18.6479, lon: 73.7756 },
  { id: 'MARKET_YARD', name: 'Market Yard', lat: 18.5119, lon: 73.8582 },
];

const MOCK_DRIVERS = Array.from({ length: 20 }, (_, i) => ({
  id: `DRV_${String(i + 1).padStart(3, '0')}`,
  name: ['Ravi Kumar', 'Suresh Patil', 'Amit Sharma', 'Rahul Jadhav', 'Vijay Shinde',
    'Prakash Desai', 'Nilesh More', 'Ganesh Pawar', 'Sachin Kulkarni', 'Ajay Kadam',
    'Deepak Bhosale', 'Rajesh Waghmare', 'Santosh Mane', 'Anil Gaikwad', 'Manoj Salve',
    'Prashant Dhole', 'Sandip Kale', 'Tushar Bhor', 'Vishwas Thorat', 'Hemant Nale'][i],
  vehicle_type: ['auto', 'cab', 'ebike'][i % 3],
  lat: 18.5726 + (Math.random() - 0.5) * 0.14,
  lon: 73.8546 + (Math.random() - 0.5) * 0.14,
  is_online: i < 16,
  is_available: i < 12,
  rating: parseFloat((3.8 + Math.random() * 1.2).toFixed(1)),
}));

const DEMAND_HISTORY = Array.from({ length: 12 }, (_, i) => ({
  hour: `${String(i * 2).padStart(2, '0')}:00`,
  demand: [20, 15, 10, 8, 12, 45, 180, 240, 190, 130, 90, 80][i],
  matched: [18, 14, 9, 7, 11, 40, 165, 220, 175, 118, 82, 74][i],
}));

const VEHICLE_COLORS = { auto: '#ff9100', cab: '#00a8ff', ebike: '#1de9b6' };
const CHART_COLORS = ['#00a8ff', '#1de9b6', '#ff9100', '#7c4dff', '#ff1744'];

function StatCard({ label, value, sub, color = 'var(--accent-blue)', icon }) {
  const displayValue = (value === undefined || value === null || (typeof value === 'number' && isNaN(value))) ? '—' : value;
  const displaySub = sub && (sub.includes('undefined') || sub.includes('NaN')) ? '' : sub;
  
  return (
    <div className="stat-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <span className="stat-label">{label}</span>
        {icon && <span style={{ fontSize: 20 }}>{icon}</span>}
      </div>
      <div className="stat-value" style={{ color }}>{displayValue}</div>
      {displaySub && <div className="stat-sub">{displaySub}</div>}
    </div>
  );
}

export default function AdminPage() {
  const [tab, setTab] = useState('map'); // map | fleet | analytics
  const [drivers, setDrivers] = useState(MOCK_DRIVERS);
  const [hotspots, setHotspots] = useState([]);
  const [predictions, setPredictions] = useState([]);
  const [trains, setTrains] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [rideStats, setRideStats] = useState({ matched: 24, pending: 3, completed: 47, total: 74, avg_wait_seconds: 187, match_rate: 0.96 });
  const [wsEvents, setWsEvents] = useState([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [simStation, setSimStation] = useState('PUNE_STATION');
  const [simDelay, setSimDelay] = useState(0);
  const [simLoad, setSimLoad] = useState(200);
  const [loading, setLoading] = useState({});
  const [surgeMode, setSurgeMode] = useState(false);
  const [timeline, setTimeline] = useState(0); // 0 | 30 | 60 (minutes)
  const [activeDisruption, setActiveDisruption] = useState(null);
  const [disruptionStation, setDisruptionStation] = useState('PUNE_STATION');
  const [disruptionIntensity, setDisruptionIntensity] = useState(0.5);
  const [hubs, setHubs] = useState([]);
  const [showHeatmap, setShowHeatmap] = useState(true);
  const wsRef = useRef(null);

  const setLoad = (key, val) => setLoading(l => ({ ...l, [key]: val }));

  const addEvent = (msg, type = 'info') => {
    const id = Date.now();
    setWsEvents(e => [{ id, msg, type, time: new Date().toLocaleTimeString() }, ...e.slice(0, 19)]);
  };

  // Load all data
  const loadData = useCallback(async () => {
    try {
      const [driverRes, hotspotRes, predRes, trainRes, dashRes, rideRes, hubRes] = await Promise.allSettled([
        getDrivers(), getHotspots(), predictAllStations(timeline), getTrains(), getAdminDashboard(), getRideStats(), getHubs()
      ]);
      if (driverRes.status === 'fulfilled') setDrivers(driverRes.value.drivers || MOCK_DRIVERS);
      if (hotspotRes.status === 'fulfilled') setHotspots(hotspotRes.value.hotspots || []);
      if (predRes.status === 'fulfilled') setPredictions(predRes.value.predictions || []);
      if (trainRes.status === 'fulfilled') setTrains((trainRes.value.trains || []).slice(0, 8));
      if (dashRes.status === 'fulfilled') setDashboard(dashRes.value);
      if (hubRes.status === 'fulfilled') setHubs(hubRes.value.hubs || []);
      if (rideRes.status === 'fulfilled') {
        const stats = rideRes.value || {};
        setRideStats({
          matched: stats.matched || 0,
          pending: stats.pending || 0,
          completed: stats.completed || 0,
          total: stats.total || 0,
          avg_wait_seconds: stats.avg_wait_seconds || 0,
          match_rate: stats.match_rate || 0
        });
      }
    } catch {}
  }, [timeline]);

  useEffect(() => {
    loadData();
    const t = setInterval(loadData, 12000);
    return () => clearInterval(t);
  }, [loadData, timeline]);

  // WebSocket admin channel
  useEffect(() => {
    const ws = createAdminWebSocket();
    wsRef.current = ws;
    ws.onopen = () => { setWsConnected(true); addEvent('🔌 Connected to real-time feed', 'success'); };
    ws.onclose = () => { setWsConnected(false); addEvent('⚠️ Disconnected', 'warning'); };
    ws.onerror = () => addEvent('❌ WebSocket error', 'danger');
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type === 'PONG') return;
        switch (data.type) {
          case 'DRIVERS_UPDATE':
            if (data.drivers?.length) setDrivers(data.drivers);
            break;
          case 'HOTSPOT_TRIGGERED':
            addEvent(`🔥 Hotspot: ${data.prediction?.station_id} — ${data.prediction?.predicted_passengers} pax`, 'warning');
            loadData();
            break;
          case 'FLEET_OPTIMIZED':
            addEvent(`✅ Fleet optimized: ${data.assignments?.length} assignments, ${Math.round((data.coverage || 0) * 100)}% coverage`, 'success');
            break;
          case 'DISRUPTION_TRIGGERED':
            addEvent(data.message, 'danger');
            setActiveDisruption(data.station_id);
            loadData();
            break;
          case 'RIDE_MATCHED':
            addEvent(`🎯 Ride matched: ${data.request_id} → Driver ${data.driver_id}`, 'success');
            break;
          case 'TRAIN_ARRIVAL_SIMULATED':
            addEvent(`🚆 Train sim at ${data.station_id}: ${data.prediction?.predicted_passengers} pax predicted`, 'info');
            loadData();
            break;
          case 'DRIVER_MOVED':
            setDrivers(d => d.map(dr => dr.id === data.driver_id ? { ...dr, lat: data.lat, lon: data.lon } : dr));
            break;
          default: break;
        }
      } catch {}
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
  }, []);

  const handleOptimize = async () => {
    setLoad('optimize', true);
    try {
      const result = await optimizeFleet(surgeMode ? 8 : 5, surgeMode);
      addEvent(`🚀 ${result.message || 'Fleet optimized'} (${result.drivers_assigned} drivers assigned)`, 'success');
      await loadData();
    } catch {
      addEvent('Failed to optimize fleet', 'danger');
    } finally {
      setLoad('optimize', false);
    }
  };

  const handleSimulate = async () => {
    setLoad('simulate', true);
    try {
      const result = await simulateArrival(simStation, parseFloat(simDelay), parseInt(simLoad));
      addEvent(`🚆 Simulated train at ${simStation}: ${simLoad} passengers`, 'info');
      await loadData();
    } catch {
      addEvent('Simulation failed', 'danger');
    } finally {
      setLoad('simulate', false);
    }
  };

  const handleTriggerDisruption = async () => {
    setLoad('disruption', true);
    try {
      await triggerDisruption(disruptionStation, parseFloat(disruptionIntensity));
      addEvent(`🚨 DISRUPTION TRIGGERED: ${disruptionStation} (Intensity: ${disruptionIntensity})`, 'danger');
      setActiveDisruption(disruptionStation);
      await loadData();
    } catch {
      addEvent('Failed to trigger disruption', 'danger');
    } finally {
      setLoad('disruption', false);
    }
  };

  const online = drivers.filter(d => d.is_online);
  const available = drivers.filter(d => d.is_available && d.is_online);
  const totalPredPax = predictions.reduce((a, p) => a + (p.predicted_passengers || 0), 0);

  const vehiclePieData = ['auto', 'cab', 'ebike'].map(t => ({
    name: t, value: drivers.filter(d => d.vehicle_type === t).length
  }));

  const stationDemandData = predictions.slice(0, 8).map(p => ({
    name: (p.station_name || p.station_id || '').replace(' Station', '').slice(0, 12),
    passengers: p.predicted_passengers || 0,
    confidence: Math.round((p.confidence || 0.8) * 100),
  }));

  return (
    <div className="page" style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Left sidebar */}
      <div style={{ width: 300, background: 'var(--bg-secondary)', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Header */}
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
            <h2 style={{ fontSize: 16, fontWeight: 700 }}>📊 Admin Console</h2>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 7, height: 7, borderRadius: '50%', background: wsConnected ? 'var(--accent-green)' : 'var(--accent-red)', boxShadow: wsConnected ? '0 0 6px var(--accent-green)' : 'none' }} />
              <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{wsConnected ? 'LIVE' : 'OFFLINE'}</span>
            </div>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>TransitSync Command Center</div>
        </div>

        {/* Quick stats */}
        <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          {[
            { l: 'Online', v: online.length, c: 'var(--accent-green)' },
            { l: 'Available', v: available.length, c: 'var(--accent-blue)' },
            { l: 'Hotspots', v: hotspots.length, c: 'var(--accent-red)' },
            { l: 'Match Rate', v: `${Math.round(rideStats.match_rate * 100)}%`, c: 'var(--accent-teal)' },
          ].map(s => (
            <div key={s.l} style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 10px', textAlign: 'center' }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: s.c }}>{s.v}</div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{s.l}</div>
            </div>
          ))}
        </div>

        {/* Controls */}
        <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Controls</div>

          {/* Surge toggle */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--bg-card)', borderRadius: 8, padding: '8px 12px', border: `1px solid ${surgeMode ? 'var(--accent-red)' : 'var(--border)'}` }}>
            <span style={{ fontSize: 13, color: surgeMode ? 'var(--accent-red)' : 'var(--text-secondary)' }}>
              🚨 Surge Mode {surgeMode ? '(8km)' : '(5km)'}
            </span>
            <div onClick={() => setSurgeMode(s => !s)} style={{
              width: 36, height: 20, borderRadius: 10, cursor: 'pointer', transition: 'all 0.2s',
              background: surgeMode ? 'var(--accent-red)' : 'var(--border)', position: 'relative',
            }}>
              <div style={{ position: 'absolute', top: 2, left: surgeMode ? 18 : 2, width: 16, height: 16, borderRadius: '50%', background: 'white', transition: 'left 0.2s' }} />
            </div>
          </div>

          <button className="btn btn-primary" onClick={handleOptimize} disabled={loading.optimize}
            style={{ width: '100%', justifyContent: 'center', fontSize: 13 }}>
            {loading.optimize ? <><span className="spinner" style={{ width: 14, height: 14 }} /> Optimizing...</> : '⚡ Optimize Fleet'}
          </button>
        </div>

        {/* Simulate arrival */}
        <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>🚆 Simulate Train Arrival</div>
          <select className="input" style={{ fontSize: 12, padding: '7px 10px' }} value={simStation} onChange={e => setSimStation(e.target.value)}>
            {STATIONS.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>DELAY (min)</div>
              <input className="input" type="number" min="0" max="30" value={simDelay}
                onChange={e => setSimDelay(e.target.value)} style={{ fontSize: 12, padding: '7px 10px' }} />
            </div>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>PASSENGERS</div>
              <input className="input" type="number" min="50" max="500" value={simLoad}
                onChange={e => setSimLoad(e.target.value)} style={{ fontSize: 12, padding: '7px 10px' }} />
            </div>
          </div>
          <button className="btn btn-success" onClick={handleSimulate} disabled={loading.simulate}
            style={{ width: '100%', justifyContent: 'center', fontSize: 13 }}>
            {loading.simulate ? <><span className="spinner" style={{ width: 14, height: 14 }} /> Simulating...</> : '🚆 Simulate Arrival'}
          </button>
        </div>

        {/* Twist 1: Simulation & Disruptions */}
        <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: 8, background: 'rgba(255, 23, 68, 0.05)' }}>
          <div style={{ fontSize: 11, color: 'var(--accent-red)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px' }}>🚨 Simulation: Disruptions</div>
          
          <select className="input" style={{ fontSize: 12, padding: '7px 10px', borderColor: 'var(--accent-red)' }} 
                  value={disruptionStation} onChange={e => setDisruptionStation(e.target.value)}>
            {STATIONS.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
            <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>INTENSITY</span>
            <input type="range" min="0.1" max="1.0" step="0.1" value={disruptionIntensity} 
                   onChange={e => setDisruptionIntensity(e.target.value)} 
                   style={{ flex: 1, accentColor: 'var(--accent-red)' }} />
            <span style={{ fontSize: 11, color: 'var(--accent-red)', fontWeight: 700 }}>{disruptionIntensity}</span>
          </div>
          
          <button className="btn" onClick={handleTriggerDisruption} disabled={loading.disruption}
            style={{ width: '100%', justifyContent: 'center', fontSize: 13, background: 'var(--accent-red)', color: 'white' }}>
            {loading.disruption ? <><span className="spinner" style={{ width: 14, height: 14 }} /> Triggering...</> : '💥 Trigger Disruption'}
          </button>
          
          {activeDisruption && (
            <div style={{ fontSize: 10, color: 'var(--accent-red)', textAlign: 'center', fontWeight: 600 }}>
              ⚠️ ACTIVE BREAKDOWN: {activeDisruption}
              <div style={{ cursor: 'pointer', textDecoration: 'underline', marginTop: 2 }} onClick={() => setActiveDisruption(null)}>Clear</div>
            </div>
          )}
        </div>

        {/* Live event feed */}
        <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '10px 16px 6px', fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            📡 Live Events
          </div>
          <div style={{ flex: 1, overflowY: 'auto', padding: '0 12px 12px' }}>
            {wsEvents.length === 0 && (
              <div style={{ color: 'var(--text-muted)', fontSize: 12, textAlign: 'center', padding: 20 }}>
                No events yet. Simulate a train arrival to start.
              </div>
            )}
            {wsEvents.map(ev => (
              <div key={ev.id} style={{
                padding: '7px 10px', borderRadius: 8, marginBottom: 6, fontSize: 12,
                background: 'var(--bg-card)', border: '1px solid var(--border)',
                borderLeft: `3px solid ${ev.type === 'success' ? 'var(--accent-green)' : ev.type === 'warning' ? 'var(--accent-orange)' : ev.type === 'danger' ? 'var(--accent-red)' : 'var(--accent-blue)'}`,
              }}>
                <div style={{ color: 'var(--text-primary)', lineHeight: 1.4 }}>{ev.msg}</div>
                <div style={{ color: 'var(--text-muted)', fontSize: 10, marginTop: 2, fontFamily: 'var(--font-mono)' }}>{ev.time}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Main content */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Tab bar */}
        <div style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)', padding: '0 20px', display: 'flex', gap: 4 }}>
          {[
            { id: 'map', label: '🗺️ Live Map' },
            { id: 'fleet', label: '🚗 Fleet Status' },
            { id: 'analytics', label: '📈 Analytics' },
          ].map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} style={{
              padding: '12px 18px', border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600,
              background: 'transparent', fontFamily: 'var(--font)',
              color: tab === t.id ? 'var(--accent-blue)' : 'var(--text-muted)',
              borderBottom: tab === t.id ? '2px solid var(--accent-blue)' : '2px solid transparent',
              transition: 'all 0.2s',
            }}>
              {t.label}
            </button>
          ))}
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12, fontSize: 12, color: 'var(--text-muted)' }}>
            <span>🚆 {trains.length} trains tracked</span>
            <span>👥 ~{totalPredPax} pax predicted</span>
            
            {/* Timeline Slider */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'var(--bg-card)', padding: '4px 12px', borderRadius: 20, border: '1px solid var(--border)' }}>
              <span style={{ fontSize: 10, fontWeight: 700 }}>TIMELINE:</span>
              {[0, 30, 60].map(m => (
                <button key={m} onClick={() => setTimeline(m)} style={{
                  padding: '2px 8px', border: 'none', borderRadius: 12, fontSize: 10, cursor: 'pointer',
                  background: timeline === m ? 'var(--accent-blue)' : 'transparent',
                  color: timeline === m ? 'white' : 'var(--text-muted)'
                }}>
                  +{m}m
                </button>
              ))}
            </div>

            <div onClick={() => setShowHeatmap(!showHeatmap)} style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: showHeatmap ? 'var(--accent-orange)' : 'var(--text-muted)' }}>
              {showHeatmap ? '🏮 Heatmap ON' : '⚪ Heatmap OFF'}
            </div>

            <span style={{ fontFamily: 'var(--font-mono)', background: 'var(--bg-card)', padding: '3px 8px', borderRadius: 6, border: '1px solid var(--border)', color: 'var(--accent-teal)' }}>
              {new Date().toLocaleTimeString()}
            </span>
          </div>
        </div>

        {/* Map tab */}
        {tab === 'map' && (
          <div style={{ flex: 1, position: 'relative' }}>
            <MapContainer center={[18.5726, 73.8546]} zoom={12} style={{ height: '100%', width: '100%' }}>
              <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="© OpenStreetMap" />

              {/* Drivers */}
              {drivers.map(d => (
                <Marker key={d.id} position={[d.lat, d.lon]}
                  icon={makeIcon(d.is_available ? (d.vehicle_type === 'auto' ? '🛺' : d.vehicle_type === 'cab' ? '🚕' : '🛵') : '⬛', d.is_available ? 26 : 16)}>
                  <Popup>
                    <div style={{ minWidth: 140 }}>
                      <strong>{d.name}</strong><br />
                      {d.vehicle_type} • ⭐{d.rating}<br />
                      🔋 Battery: {Math.round((d.battery_level || 0) * 100)}%<br />
                      Status: {d.is_available ? '🟢 Available' : d.is_online ? '🟡 On Trip' : '🔴 Offline'}
                      {d.battery_level < 0.2 && <div style={{ color: 'var(--accent-red)', fontWeight: 700, fontSize: 10, marginTop: 4 }}>⚠️ RESTRICTED (LOW BATT)</div>}
                    </div>
                  </Popup>
                </Marker>
              ))}

               {/* Hotspot heatmap circles */}
              {hotspots.map(h => (
                <React.Fragment key={h.id}>
                  <Circle center={[h.lat, h.lon]}
                    radius={600 + h.predicted_passengers * 8}
                    pathOptions={{ color: '#ff1744', fillColor: '#ff1744', fillOpacity: 0.12 + Math.min(0.3, h.predicted_passengers / 1000) }} />
                  <Marker position={[h.lat, h.lon]} icon={makeIcon('🔥', 28)}>
                    <Popup>
                      <div>
                        <strong>🔥 {h.station_name || h.station_id}</strong><br />
                        👥 {h.predicted_passengers} passengers predicted<br />
                        📊 {Math.round((h.confidence || 0.8) * 100)}% confidence
                      </div>
                    </Popup>
                  </Marker>
                </React.Fragment>
              ))}

              {/* Demand prediction circles (Heatmap) */}
              {showHeatmap && predictions.map((p, i) => p.lat && (
                <Circle key={`pred-${i}`} center={[p.lat, p.lon]}
                  radius={400 + (p.predicted_passengers * 6)}
                  pathOptions={{ 
                    color: p.ripple_multiplier > 1.2 ? 'var(--accent-red)' : 'var(--accent-blue)', 
                    fillColor: p.ripple_multiplier > 1.2 ? 'var(--accent-red)' : 'var(--accent-blue)', 
                    fillOpacity: 0.05 + Math.min(0.4, p.predicted_passengers / 500),
                    weight: p.ripple_multiplier > 1.2 ? 2 : 1,
                    dashArray: p.ripple_multiplier > 1.2 ? '5, 5' : null
                  }} />
              ))}

              {/* Stations */}
              {STATIONS.map(s => (
                <Marker key={s.id} position={[s.lat, s.lon]} icon={makeIcon(activeDisruption === s.id ? '💥' : '🚇', activeDisruption === s.id ? 32 : 22)}>
                  <Popup>
                    <div>
                      <strong>{s.name}</strong><br />
                      Metro Station
                      {activeDisruption === s.id && <div style={{ color: 'var(--accent-red)', fontWeight: 700 }}>⚠️ DISRUPTION ACTIVE</div>}
                    </div>
                  </Popup>
                </Marker>
              ))}

              {/* Charging Hubs */}
              {hubs.map(hub => (
                <Marker key={`hub-${hub.id}`} position={[hub.lat, hub.lon]} icon={makeIcon('⚡', 24)}>
                  <Popup>
                    <div style={{ minWidth: 150 }}>
                      <strong>🔋 {hub.name}</strong><br />
                      Capacity: {hub.capacity}<br />
                      Available: <span style={{ color: 'var(--accent-green)', fontWeight: 700 }}>{hub.available_spots} spots</span>
                    </div>
                  </Popup>
                </Marker>
              ))}

              {/* Train ETAs */}
              {trains.filter(t => t.lat && t.lon).map(t => (
                <Marker key={t.trip_id} position={[t.lat, t.lon]} icon={makeIcon('🚆', 22)}>
                  <Popup>
                    <div>
                      <strong>{t.station_name}</strong><br />
                      ETA: {t.minutes_until_arrival} min<br />
                      Load: {t.passenger_load} pax<br />
                      <span style={{ color: t.status === 'delayed' ? '#ff9100' : '#00e676' }}>{t.status}</span>
                    </div>
                  </Popup>
                </Marker>
              ))}
            </MapContainer>

            {/* Map Legend */}
            <div style={{ position: 'absolute', bottom: 24, right: 16, zIndex: 1000, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 10, padding: '12px 16px', fontSize: 12 }}>
              {[
                ['🛺 🚕 🛵', 'Drivers (available)'], 
                ['⬛', 'Driver (offline/busy)'], 
                ['🔌', 'Driver (charging)'],
                ['⚡', 'Charging Hub'],
                ['🔥', 'Demand Hotspot'], 
                ['🚇', 'Metro Station'], 
                ['🚆', 'Train (live)']
              ].map(([icon, label]) => (
                <div key={label} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4, color: 'var(--text-secondary)' }}>
                  <span style={{ width: 44, textAlign: 'center' }}>{icon}</span><span>{label}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Fleet tab */}
        {tab === 'fleet' && (
          <div style={{ flex: 1, overflowY: 'auto', padding: 20 }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12, marginBottom: 20 }}>
              <StatCard label="Total Fleet" value={drivers.length} sub="registered vehicles" icon="🚗" />
              <StatCard label="Online Now" value={online.length} sub={`${Math.round(online.length / drivers.length * 100)}% of fleet`} color="var(--accent-green)" icon="🟢" />
              <StatCard label="Available" value={available.length} sub="ready for pickup" color="var(--accent-blue)" icon="✅" />
              <StatCard label="Avg Rating" value={(drivers.reduce((a, d) => a + d.rating, 0) / drivers.length).toFixed(1)} sub="across all drivers" color="var(--accent-orange)" icon="⭐" />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 16, marginBottom: 20 }}>
              {/* Driver table */}
              <div className="card" style={{ overflow: 'hidden', padding: 0 }}>
                <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 700, fontSize: 14 }}>Driver Fleet ({drivers.length})</span>
                  <div style={{ display: 'flex', gap: 8 }}>
                    {['auto', 'cab', 'ebike'].map(t => (
                      <span key={t} className="badge" style={{ background: `${VEHICLE_COLORS[t]}22`, color: VEHICLE_COLORS[t], border: `1px solid ${VEHICLE_COLORS[t]}44` }}>
                        {t === 'auto' ? '🛺' : t === 'cab' ? '🚕' : '🛵'} {drivers.filter(d => d.vehicle_type === t).length}
                      </span>
                    ))}
                  </div>
                </div>
                <div style={{ maxHeight: 400, overflowY: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                    <thead>
                      <tr style={{ background: 'var(--bg-primary)' }}>
                        {['Driver', 'Type', 'Status', 'Battery', 'Rating', 'Location'].map(h => (
                          <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 600, fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {drivers.map((d, i) => (
                        <tr key={d.id} style={{ borderTop: '1px solid var(--border)', background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)' }}>
                          <td style={{ padding: '10px 14px' }}>
                            <div style={{ fontWeight: 600 }}>{d.name}</div>
                            <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{d.id}</div>
                          </td>
                          <td style={{ padding: '10px 14px' }}>
                            <span style={{ fontSize: 16 }}>{d.vehicle_type === 'auto' ? '🛺' : d.vehicle_type === 'cab' ? '🚕' : '🛵'}</span>
                          </td>
                          <td style={{ padding: '10px 14px' }}>
                            <span className={`badge ${d.is_available && d.is_online ? 'badge-green' : d.is_online ? 'badge-orange' : 'badge-red'}`}>
                              {d.is_available && d.is_online ? 'Available' : d.is_online ? 'On Trip' : 'Offline'}
                            </span>
                          </td>
                          <td style={{ padding: '10px 14px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                              <div style={{ width: 40, height: 6, background: 'var(--bg-secondary)', borderRadius: 3, overflow: 'hidden' }}>
                                <div style={{ width: `${(d.battery_level || 0) * 100}%`, height: '100%', background: (d.battery_level || 0) < 0.2 ? 'var(--accent-red)' : (d.battery_level || 0) < 0.5 ? 'var(--accent-orange)' : 'var(--accent-green)' }} />
                              </div>
                              <span style={{ fontSize: 10, fontWeight: 700, color: (d.battery_level || 0) < 0.2 ? 'var(--accent-red)' : 'var(--text-muted)' }}>
                                {Math.round((d.battery_level || 0) * 100)}%
                              </span>
                              {d.is_charging && <span style={{ fontSize: 10 }}>🔌</span>}
                            </div>
                            {(d.battery_level || 0) < 0.2 && !d.is_charging && (
                              <div style={{ fontSize: 9, color: 'var(--accent-red)', fontWeight: 600 }}>RESTRICTED</div>
                            )}
                          </td>
                          <td style={{ padding: '10px 14px', color: 'var(--accent-orange)' }}>⭐ {d.rating}</td>
                          <td style={{ padding: '10px 14px', fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                            {d.lat?.toFixed(4)}, {d.lon?.toFixed(4)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Vehicle pie */}
              <div className="card">
                <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 16 }}>Fleet Composition</div>
                <PieChart width={260} height={200}>
                  <Pie data={vehiclePieData} cx={130} cy={90} innerRadius={50} outerRadius={80} paddingAngle={3} dataKey="value">
                    {vehiclePieData.map((_, i) => (
                      <Cell key={i} fill={Object.values(VEHICLE_COLORS)[i]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-primary)' }} />
                </PieChart>
                <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap', marginTop: 8 }}>
                  {vehiclePieData.map((v, i) => (
                    <div key={v.name} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
                      <div style={{ width: 10, height: 10, borderRadius: 2, background: Object.values(VEHICLE_COLORS)[i] }} />
                      <span style={{ color: 'var(--text-secondary)', textTransform: 'capitalize' }}>{v.name}: {v.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Active hotspots */}
            <div className="card">
              <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 12 }}>🔥 Active Demand Hotspots</div>
              {hotspots.length === 0 ? (
                <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: 30, fontSize: 14 }}>
                  No active hotspots. Simulate a train arrival to generate predictions.
                </div>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12 }}>
                  {hotspots.map(h => (
                    <div key={h.id} style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', borderRadius: 10, padding: '12px 16px', borderLeft: '3px solid var(--accent-red)' }}>
                      <div style={{ fontWeight: 600, marginBottom: 4 }}>{h.station_name || h.station_id}</div>
                      <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--accent-red)', marginBottom: 4 }}>{h.predicted_passengers}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>predicted passengers</div>
                      <div style={{ marginTop: 8, background: 'var(--bg-secondary)', borderRadius: 4, height: 4, overflow: 'hidden' }}>
                        <div style={{ width: `${(h.confidence || 0.8) * 100}%`, height: '100%', background: 'var(--accent-blue)' }} />
                      </div>
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>{Math.round((h.confidence || 0.8) * 100)}% confidence</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Analytics tab */}
        {tab === 'analytics' && (
          <div style={{ flex: 1, overflowY: 'auto', padding: 20 }}>
            {/* KPI row */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12, marginBottom: 20 }}>
              <StatCard label="Total Rides (24h)" value={rideStats.total} sub={`${rideStats.matched} matched`} icon="🚖" />
              <StatCard label="Match Rate" value={`${Math.round(rideStats.match_rate * 100)}%`} sub="passenger-driver" color="var(--accent-green)" icon="🎯" />
              <StatCard label="Avg Wait Time" value={`${Math.round(rideStats.avg_wait_seconds / 60)} min`} sub={`${rideStats.avg_wait_seconds}s`} color="var(--accent-orange)" icon="⏱️" />
              <StatCard label="Predicted Pax" value={totalPredPax} sub="across all stations" color="var(--accent-purple)" icon="👥" />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
              {/* Demand history */}
              <div className="card">
                <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 16 }}>📈 Passenger Demand (24h)</div>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={DEMAND_HISTORY}>
                    <XAxis dataKey="hour" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} />
                    <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 10 }} />
                    <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-primary)' }} />
                    <Line type="monotone" dataKey="demand" stroke="#00a8ff" strokeWidth={2} dot={false} name="Demand" />
                    <Line type="monotone" dataKey="matched" stroke="#00e676" strokeWidth={2} dot={false} name="Matched" />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Station demand bar */}
              <div className="card">
                <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
                  <span>🔥 Station Demand Forecast</span>
                  <span style={{ fontSize: 10, color: 'var(--accent-green)', fontWeight: 400 }}>LIVE UPDATING</span>
                </div>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={stationDemandData.length > 0 ? stationDemandData : [
                    { name: 'Pune Stn', passengers: 185 + Math.floor(Math.random() * 20) }, 
                    { name: 'Shivajinagar', passengers: 142 + Math.floor(Math.random() * 10) },
                    { name: 'Swargate', passengers: 120 + Math.floor(Math.random() * 15) }, 
                    { name: 'PCMC', passengers: 95 + Math.floor(Math.random() * 5) },
                    { name: 'Chinchwad', passengers: 78 + Math.floor(Math.random() * 8) }, 
                    { name: 'Civil Crt', passengers: 65 + Math.floor(Math.random() * 12) },
                  ]}>
                    <XAxis dataKey="name" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} />
                    <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 10 }} />
                    <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-primary)' }} />
                    <Bar dataKey="passengers" name="Predicted Pax" radius={[4, 4, 0, 0]}>
                      {(stationDemandData.length > 6 ? stationDemandData : [1, 2, 3, 4, 5, 6]).map((_, i) => (
                        <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Upcoming trains table */}
            <div className="card" style={{ marginBottom: 16 }}>
              <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 12 }}>🚆 Live Train Feed (GTFS)</div>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ background: 'var(--bg-primary)' }}>
                    {['Station', 'ETA', 'Delay', 'Passenger Load', 'Status', 'Predicted Exit'].map(h => (
                      <th key={h} style={{ padding: '8px 14px', textAlign: 'left', fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(trains.length > 0 ? trains : [
                    { trip_id: 'T1', station_name: 'Pune Railway Station', minutes_until_arrival: 7, delay_minutes: 0, passenger_load: 220, status: 'on_time' },
                    { trip_id: 'T2', station_name: 'Shivajinagar', minutes_until_arrival: 12, delay_minutes: 2.5, passenger_load: 145, status: 'delayed' },
                    { trip_id: 'T3', station_name: 'Swargate', minutes_until_arrival: 18, delay_minutes: 0, passenger_load: 98, status: 'on_time' },
                    { trip_id: 'T4', station_name: 'PCMC', minutes_until_arrival: 22, delay_minutes: 4.1, passenger_load: 175, status: 'delayed' },
                  ]).map((t, i) => (
                    <tr key={t.trip_id} style={{ borderTop: '1px solid var(--border)', background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)' }}>
                      <td style={{ padding: '10px 14px', fontWeight: 600 }}>{t.station_name}</td>
                      <td style={{ padding: '10px 14px', color: 'var(--accent-blue)', fontFamily: 'var(--font-mono)' }}>{t.minutes_until_arrival} min</td>
                      <td style={{ padding: '10px 14px', color: t.delay_minutes > 0 ? 'var(--accent-orange)' : 'var(--accent-green)' }}>
                        {t.delay_minutes > 0 ? `+${t.delay_minutes}m` : '—'}
                      </td>
                      <td style={{ padding: '10px 14px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <div style={{ flex: 1, maxWidth: 80, background: 'var(--bg-primary)', borderRadius: 4, height: 6 }}>
                            <div style={{ width: `${Math.min(100, (t.passenger_load / 400) * 100)}%`, height: '100%', background: t.passenger_load > 300 ? 'var(--accent-red)' : 'var(--accent-blue)', borderRadius: 4 }} />
                          </div>
                          <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{t.passenger_load}</span>
                        </div>
                      </td>
                      <td style={{ padding: '10px 14px' }}>
                        <span className={`badge ${t.status === 'delayed' ? 'badge-orange' : 'badge-green'}`}>{t.status}</span>
                      </td>
                      <td style={{ padding: '10px 14px', color: 'var(--accent-teal)', fontWeight: 600 }}>
                        ~{Math.round(t.passenger_load * 0.72)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Ride stats */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12 }}>
              {[
                { label: 'Pending Rides', value: rideStats.pending, color: 'var(--accent-orange)', icon: '⏳' },
                { label: 'Matched Today', value: rideStats.matched, color: 'var(--accent-green)', icon: '✅' },
                { label: 'Completed', value: rideStats.completed, color: 'var(--accent-teal)', icon: '🏁' },
                { label: 'Surge Alerts', value: surgeMode ? '1 ACTIVE' : '0', color: surgeMode ? 'var(--accent-red)' : 'var(--text-muted)', icon: '🚨' },
              ].map(s => (
                <StatCard key={s.label} label={s.label} value={s.value} color={s.color} icon={s.icon} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
