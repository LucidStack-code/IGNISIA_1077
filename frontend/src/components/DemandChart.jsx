import { Area, AreaChart, CartesianGrid, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export default function DemandChart({ data, stations, trains }) {
  const stationNames = stations.map((s) => s.name)
  return (
    <div className='bg-slate-900 rounded border border-slate-700 p-3 h-full'>
      <h3 className='font-rajdhani text-amberx text-xl mb-2'>Demand Trend (Last 30 Ticks)</h3>
      <div className='h-[260px]'>
        <ResponsiveContainer width='100%' height='100%'>
          <AreaChart data={data}>
            <defs>
              <linearGradient id='c1' x1='0' y1='0' x2='0' y2='1'><stop offset='5%' stopColor='#22c55e' stopOpacity={0.4} /><stop offset='95%' stopColor='#22c55e' stopOpacity={0} /></linearGradient>
              <linearGradient id='c2' x1='0' y1='0' x2='0' y2='1'><stop offset='5%' stopColor='#f59e0b' stopOpacity={0.4} /><stop offset='95%' stopColor='#f59e0b' stopOpacity={0} /></linearGradient>
              <linearGradient id='c3' x1='0' y1='0' x2='0' y2='1'><stop offset='5%' stopColor='#3b82f6' stopOpacity={0.4} /><stop offset='95%' stopColor='#3b82f6' stopOpacity={0} /></linearGradient>
            </defs>
            <CartesianGrid strokeDasharray='3 3' stroke='#1f2937' />
            <XAxis dataKey='time' stroke='#94a3b8' />
            <YAxis stroke='#94a3b8' />
            <Tooltip />
            <Legend />
            {stationNames[0] && <><Area type='monotone' dataKey={stationNames[0]} stroke='#22c55e' fill='url(#c1)' animationDuration={400} /><Line type='monotone' dataKey={stationNames[0]} stroke='#22c55e' dot={false} /></>}
            {stationNames[1] && <><Area type='monotone' dataKey={stationNames[1]} stroke='#f59e0b' fill='url(#c2)' animationDuration={400} /><Line type='monotone' dataKey={stationNames[1]} stroke='#f59e0b' dot={false} /></>}
            {stationNames[2] && <><Area type='monotone' dataKey={stationNames[2]} stroke='#3b82f6' fill='url(#c3)' animationDuration={400} /><Line type='monotone' dataKey={stationNames[2]} stroke='#3b82f6' dot={false} /></>}
            {trains.filter((t) => t.status === 'ARRIVED').map((t) => <ReferenceLine key={t.id} x={(data[data.length - 1] || {}).time} stroke='#ef4444' strokeDasharray='4 4' />)}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
