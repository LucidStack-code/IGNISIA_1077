import { useMemo } from 'react'
import LiveMap from '../components/LiveMap'
import TrainArrivalBoard from '../components/TrainArrivalBoard'
import KPIPanel from '../components/KPIPanel'
import DemandChart from '../components/DemandChart'
import LogPanel from '../components/LogPanel'
import SurgeAlert from '../components/SurgeAlert'
import { useTransit } from '../context/TransitContext'

export default function AdminDashboard() {
  const { state, status, retryCountdown, send, theme, toggleTheme } = useTransit()
  const stationsById = useMemo(() => Object.fromEntries(state.stations.map((s) => [s.id, s])), [state.stations])
  const surgeNames = state.stations.filter((s) => state.surge_stations.includes(s.id)).map((s) => s.name)
  const isLoading = status === 'connecting'

  return (
    <div className={`${theme === 'dark' ? 'bg-navy text-slate-100' : 'bg-slate-100 text-slate-900'} min-h-screen p-3 md:p-4 font-rajdhani ${state.surge_active ? 'border-4 border-red-500 animate-pulse' : ''}`}>
      <SurgeAlert active={state.surge_active} stations={surgeNames} />
      <div className='grid grid-cols-1 lg:grid-cols-[240px_1fr] gap-3'>
        <aside className='bg-black/40 rounded border border-slate-700 p-3 space-y-3'>
          <h1 className='text-2xl text-amberx font-bold'>TransitMind AI</h1>
          <div className='text-xs font-monojet'>Sim Time: {state.sim_time ? new Date(state.sim_time).toLocaleTimeString() : '--'}</div>
          <div className='text-xs font-monojet'>WS: {status}{status === 'reconnecting' ? ` (${retryCountdown}s)` : ''}</div>
          <button onClick={() => send({ type: 'TRIGGER_DEMO' })} className='w-full bg-red-600 hover:bg-red-500 text-white py-2 rounded animate-pulse'>▶ Trigger Demo: Deccan Express Delay</button>
          <div className='space-y-2'>
            <label className='text-sm'>Delay Train</label>
            <select id='trainId' className='w-full bg-slate-900 border border-slate-600 rounded px-2 py-1 text-sm'>{state.trains.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select>
            <input id='delayMins' type='number' defaultValue={5} className='w-full bg-slate-900 border border-slate-600 rounded px-2 py-1 text-sm' />
            <button className='w-full bg-amber-600 hover:bg-amber-500 text-black font-semibold py-1 rounded' onClick={() => {
              const trainId = Number(document.getElementById('trainId')?.value)
              const delay = Number(document.getElementById('delayMins')?.value || 0)
              send({ type: 'TRIGGER_DELAY', train_id: trainId, delay_minutes: delay })
            }}>Apply Delay</button>
          </div>
          <div className='space-y-2'>
            <div className='text-sm'>Sim Speed</div>
            <div className='grid grid-cols-3 gap-1'>
              {[1, 2, 5].map((speed) => <button key={speed} className='bg-slate-700 hover:bg-slate-600 rounded py-1 text-sm' onClick={() => send({ type: 'SET_SPEED', speed })}>{speed}x</button>)}
            </div>
          </div>
          <button onClick={toggleTheme} className='w-full bg-slate-700 rounded py-2 text-sm'>Toggle {theme === 'dark' ? 'Light' : 'Dark'}</button>
        </aside>

        <main className='space-y-3'>
          {isLoading ? (
            <div className='h-72 rounded border border-slate-600 flex items-center justify-center'>Connecting to simulation...</div>
          ) : status === 'failed' ? (
            <div className='h-72 rounded border border-red-500 flex items-center justify-center'>Connection failed after retries.</div>
          ) : (
            <div className='grid grid-cols-1 xl:grid-cols-[60%_40%] gap-3'>
              <div className='h-[420px] rounded overflow-hidden border border-slate-700'><LiveMap stations={state.stations} vehicles={state.vehicles} surgeStations={state.surge_stations} /></div>
              <DemandChart data={state.demand_series} stations={state.stations} trains={state.trains} />
            </div>
          )}
          <KPIPanel metrics={state.metrics} />
          <TrainArrivalBoard trains={state.trains} stationsById={stationsById} />
          <LogPanel logs={state.logs} />
        </main>
      </div>
    </div>
  )
}
