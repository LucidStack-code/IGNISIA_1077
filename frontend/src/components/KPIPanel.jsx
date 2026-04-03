import { useEffect, useState } from 'react'
import { formatPct } from '../utils/formatters'

function AnimatedValue({ value, suffix = '' }) {
  const [display, setDisplay] = useState(0)
  useEffect(() => {
    const start = display
    const diff = value - start
    let frame = 0
    const total = 20
    const timer = setInterval(() => {
      frame += 1
      const next = start + (diff * frame) / total
      setDisplay(next)
      if (frame >= total) clearInterval(timer)
    }, 20)
    return () => clearInterval(timer)
  }, [value])

  return <div className='text-3xl font-monojet'>{suffix === '%' ? formatPct(display) : `${display.toFixed(1)}${suffix}`}</div>
}

export default function KPIPanel({ metrics }) {
  const cards = [
    { label: 'Matching Efficiency', value: metrics.matching_efficiency || 0, suffix: '%', color: 'text-emerald-400' },
    { label: 'Fleet Utilization', value: metrics.fleet_utilization || 0, suffix: '%', color: 'text-amber-400' },
    { label: 'Avg Wait Time', value: metrics.avg_wait_time || 0, suffix: 'm', color: 'text-sky-400' },
    { label: 'Unmet Demand', value: metrics.unmet_demand_pct || 0, suffix: '%', color: 'text-rose-400' }
  ]

  return (
    <div className='grid grid-cols-2 lg:grid-cols-4 gap-3'>
      {cards.map((c) => (
        <div key={c.label} className='bg-slate-900 rounded border border-slate-700 p-3'>
          <div className='text-xs uppercase tracking-wide text-slate-400'>{c.label}</div>
          <div className={c.color}><AnimatedValue value={c.value} suffix={c.suffix} /></div>
        </div>
      ))}
    </div>
  )
}
