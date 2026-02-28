import { motion } from 'framer-motion'

interface RadialGaugeProps {
  value: number
  max?: number
  label: string
  color?: 'cyan' | 'magenta' | 'green' | 'orange' | 'red' | 'purple'
  size?: 'sm' | 'md' | 'lg'
  showValue?: boolean
  thresholds?: { warning: number; critical: number }
}

const colorMap = {
  cyan: '#00FFE5',
  magenta: '#FF00FF',
  green: '#39FF14',
  orange: '#FF6B00',
  red: '#FF2D55',
  purple: '#B14EFF',
}

const sizeMap = {
  sm: { size: 60, stroke: 6, fontSize: 'text-xs' },
  md: { size: 80, stroke: 8, fontSize: 'text-sm' },
  lg: { size: 120, stroke: 10, fontSize: 'text-lg' },
}

export default function RadialGauge({
  value,
  max = 100,
  label,
  color = 'cyan',
  size = 'md',
  showValue = true,
  thresholds,
}: RadialGaugeProps) {
  const config = sizeMap[size]
  const percentage = Math.min((value / max) * 100, 100)
  const radius = (config.size - config.stroke) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (percentage / 100) * circumference

  // Determine color based on thresholds
  let activeColor = colorMap[color]
  if (thresholds) {
    if (percentage >= thresholds.critical) activeColor = colorMap.red
    else if (percentage >= thresholds.warning) activeColor = colorMap.orange
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: config.size, height: config.size }}>
        {/* Background circle */}
        <svg className="w-full h-full -rotate-90" viewBox={`0 0 ${config.size} ${config.size}`}>
          <circle
            cx={config.size / 2}
            cy={config.size / 2}
            r={radius}
            fill="none"
            stroke="rgba(255,255,255,0.1)"
            strokeWidth={config.stroke}
          />
          {/* Progress arc */}
          <motion.circle
            cx={config.size / 2}
            cy={config.size / 2}
            r={radius}
            fill="none"
            stroke={activeColor}
            strokeWidth={config.stroke}
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: 1, ease: 'easeOut' }}
            style={{
              filter: `drop-shadow(0 0 6px ${activeColor})`,
            }}
          />
        </svg>
        {/* Center value */}
        {showValue && (
          <div className="absolute inset-0 flex items-center justify-center">
            <motion.span
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.5, duration: 0.3 }}
              className={`font-bold ${config.fontSize} font-mono`}
              style={{ color: activeColor }}
            >
              {Math.round(percentage)}%
            </motion.span>
          </div>
        )}
      </div>
      <span className="text-xs text-text-secondary text-center">{label}</span>
    </div>
  )
}
