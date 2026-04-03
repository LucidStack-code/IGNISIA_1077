import { useEffect, useState } from 'react'

export default function SurgeAlert({ active, stations }) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (active) {
      setVisible(true)
      const timer = setTimeout(() => setVisible(false), 4000)
      return () => clearTimeout(timer)
    }
    setVisible(false)
  }, [active])

  if (!visible) return null
  return (
    <div className='fixed inset-0 bg-red-900/40 flex items-center justify-center z-[9999]'>
      <div className='bg-red-950 border border-red-400 text-red-100 p-6 rounded text-center shadow-2xl animate-pulse'>
        ⚡ SURGE — {stations.join(', ') || 'Station'} — Emergency fleet deploying
      </div>
    </div>
  )
}
