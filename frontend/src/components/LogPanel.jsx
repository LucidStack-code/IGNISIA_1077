import { useMemo, useState } from 'react'

const COLORS = {
  SURGE_DISPATCHED: 'text-red-400',
  PRE_POSITIONED: 'text-purple-300',
  DEPLOYED: 'text-yellow-300',
  REROUTED: 'text-blue-300',
  RETURNED: 'text-slate-400',
  ARRIVAL: 'text-emerald-300'
}

export default function LogPanel({ logs = [] }) {
  const [filter, setFilter] = useState('ALL')
  const filtered = useMemo(() => {
    if (filter === 'ALL') return logs
    if (filter === 'SURGE') return logs.filter((l) => `${l.action}`.includes('SURGE'))
    if (filter === 'DEPLOY') return logs.filter((l) => `${l.action}`.includes('DEPLOY'))
    if (filter === 'REROUTE') return logs.filter((l) => `${l.action}`.includes('REROUTE'))
    if (filter === 'PRE-POSITION') return logs.filter((l) => `${l.action}`.includes('PRE_POSITION'))
    return logs
  }, [logs, filter])

  return (
    <div className='bg-slate-900 rounded border border-slate-700 p-3 h-[240px] flex flex-col'>
      <div className='flex items-center justify-between mb-2'>
        <h3 className='font-rajdhani text-amberx text-xl'>Log Panel</h3>
        <select value={filter} onChange={(e) => setFilter(e.target.value)} className='bg-slate-800 text-xs border border-slate-600 rounded px-2 py-1'>
          {['ALL', 'SURGE', 'DEPLOY', 'REROUTE', 'PRE-POSITION'].map((f) => <option key={f}>{f}</option>)}
        </select>
      </div>
      <div className='overflow-auto text-xs font-monojet space-y-1'>
        {filtered.slice(-50).reverse().map((l, idx) => (
          <div key={`${l.timestamp}-${idx}`} className={COLORS[l.action] || 'text-slate-300'}>[{(l.timestamp || '').slice(11, 19)}] {l.action}: {l.reason}</div>
        ))}
      </div>
    </div>
  )
}
