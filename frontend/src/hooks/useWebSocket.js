import { useCallback, useEffect, useRef, useState } from 'react'

export default function useWebSocket(url, onMessage) {
  const socketRef = useRef(null)
  const retriesRef = useRef(0)
  const reconnectTimerRef = useRef(null)
  const [status, setStatus] = useState('connecting')
  const [retryCountdown, setRetryCountdown] = useState(0)

  const connect = useCallback(() => {
    if (socketRef.current && socketRef.current.readyState <= 1) return

    setStatus('connecting')
    const ws = new WebSocket(url)
    socketRef.current = ws

    ws.onopen = () => {
      retriesRef.current = 0
      setStatus('connected')
      ws.send(JSON.stringify({ type: 'REQUEST_SNAPSHOT' }))
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onMessage?.(data)
      } catch {
      }
    }

    ws.onclose = () => {
      if (retriesRef.current >= 5) {
        setStatus('failed')
        return
      }
      retriesRef.current += 1
      const delay = Math.min(16000, 1000 * (2 ** retriesRef.current))
      const secs = Math.ceil(delay / 1000)
      setRetryCountdown(secs)
      setStatus('reconnecting')

      reconnectTimerRef.current = setTimeout(() => connect(), delay)
      const countdown = setInterval(() => {
        setRetryCountdown((prev) => {
          if (prev <= 1) {
            clearInterval(countdown)
            return 0
          }
          return prev - 1
        })
      }, 1000)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [url, onMessage])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      if (socketRef.current) socketRef.current.close()
    }
  }, [connect])

  const send = useCallback((payload) => {
    const ws = socketRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(payload))
    }
  }, [])

  return { status, retryCountdown, send }
}
