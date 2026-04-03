import { formatNumber } from '../utils/formatters'

export default function TrainArrivalBoard({ trains, stationsById }) {
  return (
    <div className='bg-black/50 rounded border border-amberx/40 p-3 overflow-auto'>
      <h3 className='font-rajdhani text-amberx text-xl mb-2'>Train Arrival Board</h3>
      <table className='w-full text-xs md:text-sm font-monojet text-green-300'>
        <thead>
          <tr className='text-amberx border-b border-amberx/40'>
            <th className='text-left p-1'>Train</th>
            <th className='text-left p-1'>Number</th>
            <th className='text-left p-1'>Arrives In</th>
            <th className='text-left p-1'>Coaches</th>
            <th className='text-left p-1'>Expected Pax</th>
            <th className='text-left p-1'>Status</th>
            <th className='text-left p-1'>Formula</th>
          </tr>
        </thead>
        <tbody>
          {trains.map((t) => (
            <tr key={t.id} className={`${t.is_delayed ? 'bg-red-900/50 text-red-300' : ''} border-b border-slate-700`}>
              <td className='p-1'>{t.name} ({stationsById[t.station_id]?.name || 'N/A'})</td>
              <td className='p-1'>{t.train_number}</td>
              <td className='p-1'>{t.status === 'ARRIVED' ? 'Arrived' : `${Math.max(0, t.eta_minutes)} min`}</td>
              <td className='p-1'>{t.coach_count}</td>
              <td className='p-1'>{formatNumber(t.expected_passengers)}</td>
              <td className='p-1'>{t.status}</td>
              <td className='p-1 text-slate-200'>{t.formula}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
