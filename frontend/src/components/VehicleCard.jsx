import { emojiForVehicle } from '../utils/formatters'

export default function VehicleCard({ vehicle, etaMinutes, onBook }) {
  return (
    <div className='rounded border border-orange-200 p-3 bg-white shadow-sm'>
      <div className='flex items-center justify-between'>
        <div className='font-semibold text-slate-800'>{emojiForVehicle(vehicle.vehicle_type)} {vehicle.label}</div>
        <div className='text-xs text-slate-500'>{vehicle.status}</div>
      </div>
      <div className='text-sm text-slate-600 mt-1'>ETA: {etaMinutes} min</div>
      <div className='text-sm text-slate-600'>Capacity: {vehicle.capacity}</div>
      <button onClick={onBook} className='mt-2 w-full rounded bg-saffron text-white py-1.5 text-sm hover:opacity-90'>Book Ride</button>
    </div>
  )
}
