import { motion, HTMLMotionProps } from 'framer-motion'
import { forwardRef } from 'react'

type Variant = 'default' | 'subtle' | 'elevated' | 'card'

interface GlassPanelProps extends Omit<HTMLMotionProps<'div'>, 'ref'> {
  variant?: Variant
  glow?: boolean
  scanLine?: boolean
  padding?: 'none' | 'sm' | 'md' | 'lg'
}

const variantStyles: Record<Variant, string> = {
  default: 'glass-panel',
  subtle: 'glass-panel-subtle',
  elevated: 'bg-bg-elevated/80 backdrop-blur-glass border border-glass-border rounded-xl shadow-card',
  card: 'glass-card',
}

const paddingStyles = {
  none: '',
  sm: 'p-3',
  md: 'p-4',
  lg: 'p-6',
}

const GlassPanel = forwardRef<HTMLDivElement, GlassPanelProps>(
  ({ variant = 'default', glow = false, scanLine = false, padding = 'md', className = '', children, ...props }, ref) => {
    return (
      <motion.div
        ref={ref}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: 'easeOut' }}
        className={`
          ${variantStyles[variant]}
          ${paddingStyles[padding]}
          ${glow ? 'animate-border-glow' : ''}
          ${scanLine ? 'scan-line' : ''}
          ${className}
        `}
        {...props}
      >
        {children}
      </motion.div>
    )
  }
)

GlassPanel.displayName = 'GlassPanel'

export default GlassPanel
