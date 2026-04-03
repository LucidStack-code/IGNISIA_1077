import { CircleMarker, MapContainer, Marker, Popup, TileLayer } from 'react-leaflet'
import L from 'leaflet'
import { emojiForVehicle } from '../utils/formatters'

const stationColor = (level) => {
  if (level === 'LOW') return '#22c55e'
  if (level === 'MEDIUM') return '#eab308'
  if (level === 'HIGH') return '#f97316'
  return '#ef4444'
}

const vehicleIcon = (vehicle) =>
  L.divIcon({
    html: `<div style="font-size:20px">${emojiForVehicle(vehicle.vehicle_type)}</div>`,
    className: '',
    iconSize: [20, 20]
  })

export default function LiveMap({ stations, vehicles, surgeStations = [] }) {
  const center = stations[0] ? [stations[0].lat, stations[0].lng] : [18.5284, 73.8744]

  return (
    <MapContainer center={center} zoom={13} style={{ height: '100%', width: '100%' }}>
      <TileLayer attribution='&copy; OpenStreetMap contributors' url='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png' />
      {stations.map((s) => (
        <CircleMarker key={s.id} center={[s.lat, s.lng]} radius={surgeStations.includes(s.id) ? 16 : 11} pathOptions={{ color: stationColor(s.demand_level), fillColor: stationColor(s.demand_level), fillOpacity: 0.5 }}>
          <Popup>
            <div className='font-mono text-sm'>
              <div className='font-bold'>{s.name}</div>
              <div>Demand: {s.current_demand}</div>
              <div>Vehicles: {s.assigned_vehicles}</div>
              <div>Type: {s.station_type}</div>
            </div>
          </Popup>
        </CircleMarker>
      ))}
      {vehicles.map((v) => (
        <Marker key={v.id} position={[v.current_lat, v.current_lng]} icon={vehicleIcon(v)}>
          <Popup>
            <div className='font-mono text-sm'>
              <div className='font-bold'>{v.label}</div>
              <div>Status: {v.status}</div>
              <div>Capacity: {v.capacity}</div>
            </div>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  )
}
