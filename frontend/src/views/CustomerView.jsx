import { useMemo, useState } from 'react'
import { MapContainer, Marker, Popup, TileLayer } from 'react-leaflet'
import L from 'leaflet'
import { useTransit } from '../context/TransitContext'
import { demandColor, formatNumber, emojiForVehicle } from '../utils/formatters'
import VehicleCard from '../components/VehicleCard'
import BookRideModal from '../components/BookRideModal'

const icon = (v) => L.divIcon({ html: `<div style="font-size:18px">${emojiForVehicle(v.vehicle_type)}</div>`, className: '', iconSize: [18, 18] })

function dist(a, b) {
  return Math.sqrt((a.lat - b.current_lat) ** 2 + (a.lng - b.current_lng) ** 2)
}

export default function CustomerView() {
  const { state, status, retryCountdown, send, lastRideResult, clearRideResult, theme, toggleTheme } = useTransit()
  const [selectedStation, setSelectedStation] = useState(null)
  const [bookVehicle, setBookVehicle] = useState(null)

  const station = selectedStation ? state.stations.find((s) => s.id === Number(selectedStation)) : state.stations[0]

  const nextTrain = useMemo(() => {
    if (!station) return null
    return [...state.trains].filter((t) => t.station_id === station.id && t.status !== 'ARRIVED').sort((a, b) => a.eta_minutes - b.eta_minutes)[0]
  }, [state.trains, station])

  const nearbyVehicles = useMemo(() => {
    if (!station) return []
    return state.vehicles.filter((v) => dist(station, v) <= 0.01).sort((a, b) => dist(station, a) - dist(station, b))
  }, [station, state.vehicles])

  return (
    <div className={`${theme === 'dark' ? 'bg-slate-900 text-white' : 'bg-white text-slate-900'} min-h-screen font-poppins p-3`}>
      <header className='flex items-center justify-between mb-3'>
        <div>
          <div className='text-xl font-bold text-saffron'>TransitMind</div>
          <div className='text-xs'>Sim: {state.sim_time ? new Date(state.sim_time).toLocaleTimeString() : '--'}</div>
        </div>
        <div className='flex items-center gap-2 text-xs'>
          <span className={`h-2.5 w-2.5 rounded-full ${status === 'connected' ? 'bg-green-500' : 'bg-red-500'}`} />
          {status === 'reconnecting' ? `Reconnecting ${retryCountdown}s` : status}
          <button onClick={toggleTheme} className='ml-2 border px-2 py-1 rounded'>Theme</button>
        </div>
      </header>

      <div className='mb-3'>
        <label className='text-sm font-medium'>Station Selector</label>
        <select className='w-full border rounded p-2 mt-1' value={station?.id || ''} onChange={(e) => setSelectedStation(e.target.value)}>
          {state.stations.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
      </div>

      {nextTrain && (
        <div className='rounded border p-3 mb-3'>
          <div className='font-rajdhani text-lg'>{nextTrain.name} arrives in {Math.max(0, nextTrain.eta_minutes)} min</div>
          <div className='text-sm mt-1'>Expected passengers: {formatNumber(nextTrain.expected_passengers)}</div>
          <div className='text-sm'>Formula: {nextTrain.formula}</div>
          <div className={`mt-1 text-sm font-semibold ${demandColor(station?.demand_level)}`}>Demand: {station?.demand_level}</div>
        </div>
      )}

      <div className='grid grid-cols-1 gap-2 mb-3'>
        {nearbyVehicles.map((v) => (
          <VehicleCard key={v.id} vehicle={v} etaMinutes={Math.max(1, Math.round(dist(station, v) / 0.001))} onBook={() => {
            clearRideResult()
            setBookVehicle(v)
          }} />
        ))}
      </div>

      {station && (
        <div className='h-56 rounded overflow-hidden border mb-4'>
          <MapContainer center={[station.lat, station.lng]} zoom={14} style={{ height: '100%', width: '100%' }}>
            <TileLayer attribution='&copy; OpenStreetMap contributors' url='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png' />
            <Marker position={[station.lat, station.lng]}><Popup>{station.name}</Popup></Marker>
            {nearbyVehicles.map((v) => <Marker key={v.id} position={[v.current_lat, v.current_lng]} icon={icon(v)}><Popup>{v.label}</Popup></Marker>)}
          </MapContainer>
        </div>
      )}

      <BookRideModal open={Boolean(bookVehicle)} vehicle={bookVehicle} stationId={station?.id} send={send} result={lastRideResult} onClose={() => setBookVehicle(null)} />
    </div>
  )
}
