import { useEffect } from 'react'

export default function BookRideModal({ open, vehicle, stationId, send, result, onClose }) {
  useEffect(() => {
    if (!open || !vehicle) return
    send({ type: 'BOOK_RIDE', from_lat: vehicle.current_lat, from_lng: vehicle.current_lng, to_station_id: stationId })
  }, [open])

  if (!open) return null
  return (
    <div className='fixed inset-0 bg-black/40 flex items-center justify-center z-50'>
      <div className='bg-white rounded p-4 w-[90%] max-w-sm'>
        <h3 className='font-semibold text-lg text-slate-900 mb-2'>Book Ride</h3>
        <p className='text-sm text-slate-600 mb-3'>Confirming ride assignment...</p>
        {result ? (
          <div className='text-sm mb-3 text-slate-700'>{result.ok ? <>Assigned vehicle: <span className='font-semibold'>{result.vehicle}</span><br />ETA: {result.eta_minutes} min</> : (result.message || 'High demand — join waitlist')}</div>
        ) : (
          <div className='text-sm mb-3 text-slate-500'>Waiting for assignment...</div>
        )}
        <button onClick={onClose} className='w-full rounded bg-slate-900 text-white py-2'>Close</button>
      </div>
    </div>
  )
}
