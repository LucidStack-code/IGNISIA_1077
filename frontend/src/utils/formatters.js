export const demandColor = (level) => {
  switch (level) {
    case 'LOW':
      return 'text-green-400'
    case 'MEDIUM':
      return 'text-yellow-300'
    case 'HIGH':
      return 'text-orange-400'
    case 'SURGE':
      return 'text-red-500'
    default:
      return 'text-slate-300'
  }
}

export const formatNumber = (value) => new Intl.NumberFormat('en-IN').format(Math.round(value || 0))
export const formatPct = (value) => `${(value || 0).toFixed(1)}%`

export const emojiForVehicle = (type) => {
  if (type === 'AUTO') return '🛺'
  if (type === 'EBIKE') return '🚲'
  return '🚕'
}
