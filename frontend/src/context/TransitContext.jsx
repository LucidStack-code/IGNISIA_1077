import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import useWebSocket from '../hooks/useWebSocket'

const TransitContext = createContext(null)

const defaultState = {
  sim_time: null,
  stations: [],
  vehicles: [],
  trains: [],
  metrics: {
    matching_efficiency: 0,
    fleet_utilization: 0,
    avg_wait_time: 0,
    unmet_demand_pct: 0
  },
  logs: [],
  surge_active: false,
  surge_stations: [],
  formula_snapshots: [],
  demand_series: []
}

export function TransitProvider({ children }) {
  const [state, setState] = useState(defaultState)
  const [lastRideResult, setLastRideResult] = useState(null)
  const [theme, setTheme] = useState(localStorage.getItem('transit_theme') || 'dark')

  const onMessage = useCallback((message) => {
    if (message.type === 'STATE_UPDATE') {
      setState((prev) => ({ ...prev, ...message }))
    } else if (message.type === 'SURGE_ALERT') {
      setState((prev) => ({ ...prev, surge_active: true }))
    } else if (message.type === 'BOOK_RIDE_RESULT') {
      setLastRideResult(message)
    }
  }, [])

  const wsUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.hostname}:8000/ws`
  const { status, retryCountdown, send } = useWebSocket(wsUrl, onMessage)

  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    localStorage.setItem('transit_theme', next)
  }

  const value = useMemo(
    () => ({
      state,
      status,
      retryCountdown,
      send,
      theme,
      toggleTheme,
      lastRideResult,
      clearRideResult: () => setLastRideResult(null)
    }),
    [state, status, retryCountdown, send, theme, lastRideResult]
  )

  return <TransitContext.Provider value={value}>{children}</TransitContext.Provider>
}

export function useTransit() {
  const ctx = useContext(TransitContext)
  if (!ctx) throw new Error('useTransit must be used inside TransitProvider')
  return ctx
}
