import { cn } from '@/lib/utils'

interface SkeletonProps {
  className?: string
}

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn('bg-border rounded animate-pulse', className)}
    />
  )
}

export function SkeletonCard({ className }: SkeletonProps) {
  return (
    <div className={cn('bg-card border border-border rounded-lg p-3', className)}>
      <div className="flex items-center gap-3">
        <Skeleton className="w-8 h-8 rounded" />
        <div className="space-y-1.5 flex-1">
          <Skeleton className="w-16 h-5" />
          <Skeleton className="w-24 h-3" />
        </div>
      </div>
    </div>
  )
}

export function SkeletonListItem({ className }: SkeletonProps) {
  return (
    <div className={cn('bg-card border border-border rounded-lg p-3', className)}>
      <div className="flex items-center gap-2 mb-2">
        <Skeleton className="w-12 h-5 rounded" />
        <Skeleton className="w-24 h-3" />
      </div>
      <Skeleton className="w-3/4 h-4" />
    </div>
  )
}

export function SkeletonText({ lines = 1, className }: SkeletonProps & { lines?: number }) {
  return (
    <div className={cn('space-y-2', className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className={cn('h-4', i === lines - 1 ? 'w-2/3' : 'w-full')}
        />
      ))}
    </div>
  )
}
