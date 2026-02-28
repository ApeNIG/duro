import { motion } from 'framer-motion'
import { LucideIcon } from 'lucide-react'

interface SectionHeaderProps {
  title: string
  icon?: LucideIcon
  action?: React.ReactNode
  badge?: string | number
  badgeColor?: 'cyan' | 'magenta' | 'green' | 'orange' | 'red' | 'purple' | 'blue'
}

export default function SectionHeader({
  title,
  icon: Icon,
  action,
  badge,
  badgeColor = 'cyan',
}: SectionHeaderProps) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3 }}
      className="section-header"
    >
      <div className="flex items-center gap-3">
        {Icon && (
          <Icon className="w-4 h-4 text-neon-cyan" />
        )}
        <span className="section-header-title">{title}</span>
        {badge !== undefined && (
          <span className={`badge badge-${badgeColor}`}>
            {badge}
          </span>
        )}
      </div>
      {action && (
        <div className="flex-shrink-0">
          {action}
        </div>
      )}
    </motion.div>
  )
}
