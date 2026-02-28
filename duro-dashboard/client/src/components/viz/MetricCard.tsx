import { motion, useMotionValue, useTransform, animate } from 'framer-motion'
import { useEffect } from 'react'
import { LucideIcon, TrendingUp, TrendingDown, Minus } from 'lucide-react'

interface MetricCardProps {
  label: string
  value: number
  previousValue?: number
  format?: 'number' | 'percent' | 'duration'
  icon?: LucideIcon
  color?: 'cyan' | 'magenta' | 'green' | 'orange' | 'purple' | 'blue' | 'red'
  glow?: boolean
  compact?: boolean
}

const colorMap = {
  cyan: {
    bg: 'from-neon-cyan/10 to-transparent',
    text: 'text-neon-cyan',
    border: 'border-neon-cyan/30',
    glow: 'shadow-neon-cyan',
  },
  magenta: {
    bg: 'from-neon-magenta/10 to-transparent',
    text: 'text-neon-magenta',
    border: 'border-neon-magenta/30',
    glow: 'shadow-neon-magenta',
  },
  green: {
    bg: 'from-neon-green/10 to-transparent',
    text: 'text-neon-green',
    border: 'border-neon-green/30',
    glow: 'shadow-neon-green',
  },
  orange: {
    bg: 'from-neon-orange/10 to-transparent',
    text: 'text-neon-orange',
    border: 'border-neon-orange/30',
    glow: 'shadow-neon-orange',
  },
  purple: {
    bg: 'from-neon-purple/10 to-transparent',
    text: 'text-neon-purple',
    border: 'border-neon-purple/30',
    glow: 'shadow-neon-purple',
  },
  blue: {
    bg: 'from-neon-blue/10 to-transparent',
    text: 'text-neon-blue',
    border: 'border-neon-blue/30',
    glow: 'shadow-neon-blue',
  },
  red: {
    bg: 'from-neon-red/10 to-transparent',
    text: 'text-neon-red',
    border: 'border-neon-red/30',
    glow: 'shadow-neon-red',
  },
}

function formatValue(value: number, format: 'number' | 'percent' | 'duration'): string {
  switch (format) {
    case 'percent':
      return `${value.toFixed(1)}%`
    case 'duration':
      if (value < 60) return `${value}s`
      if (value < 3600) return `${Math.floor(value / 60)}m`
      return `${Math.floor(value / 3600)}h`
    default:
      if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`
      if (value >= 1000) return `${(value / 1000).toFixed(1)}K`
      return value.toLocaleString()
  }
}

function AnimatedNumber({ value, format }: { value: number; format: 'number' | 'percent' | 'duration' }) {
  const motionValue = useMotionValue(0)
  const rounded = useTransform(motionValue, (v) => formatValue(Math.round(v), format))

  useEffect(() => {
    const controls = animate(motionValue, value, {
      duration: 1,
      ease: 'easeOut',
    })
    return controls.stop
  }, [value, motionValue])

  return <motion.span>{rounded}</motion.span>
}

export default function MetricCard({
  label,
  value,
  previousValue,
  format = 'number',
  icon: Icon,
  color = 'cyan',
  glow = false,
  compact = false,
}: MetricCardProps) {
  const colors = colorMap[color]
  const change = previousValue !== undefined ? ((value - previousValue) / previousValue) * 100 : null
  const isPositive = change !== null && change > 0
  const isNegative = change !== null && change < 0

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ scale: 1.02 }}
      transition={{ duration: 0.2 }}
      className={`
        glass-card ${compact ? 'p-3' : 'p-4'}
        bg-gradient-to-br ${colors.bg}
        border ${colors.border}
        ${glow ? colors.glow : ''}
      `}
    >
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-xs font-medium text-text-secondary uppercase tracking-wider">
            {label}
          </p>
          <p className={`${compact ? 'text-xl' : 'text-3xl'} font-bold ${colors.text} metric-value ${glow ? 'metric-glow' : ''}`}>
            <AnimatedNumber value={value} format={format} />
          </p>
          {change !== null && (
            <div className="flex items-center gap-1 mt-1">
              {isPositive && <TrendingUp className="w-3 h-3 text-neon-green" />}
              {isNegative && <TrendingDown className="w-3 h-3 text-neon-red" />}
              {!isPositive && !isNegative && <Minus className="w-3 h-3 text-text-muted" />}
              <span className={`text-xs ${isPositive ? 'text-neon-green' : isNegative ? 'text-neon-red' : 'text-text-muted'}`}>
                {isPositive ? '+' : ''}{change.toFixed(1)}%
              </span>
            </div>
          )}
        </div>
        {Icon && (
          <div className={`p-2 rounded-lg bg-bg-card/50 ${colors.text}`}>
            <Icon className={`${compact ? 'w-4 h-4' : 'w-5 h-5'}`} />
          </div>
        )}
      </div>
    </motion.div>
  )
}
