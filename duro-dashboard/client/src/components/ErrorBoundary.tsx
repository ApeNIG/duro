import { Component, ErrorInfo, ReactNode } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  }

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo)
  }

  public render() {
    if (this.state.hasError) {
      return (
        this.props.fallback || (
          <ErrorState
            title="Something went wrong"
            message={this.state.error?.message || 'An unexpected error occurred'}
            onRetry={() => this.setState({ hasError: false, error: null })}
          />
        )
      )
    }

    return this.props.children
  }
}

interface ErrorStateProps {
  title?: string
  message?: string
  onRetry?: () => void
  compact?: boolean
}

export function ErrorState({
  title = 'Error',
  message = 'Something went wrong',
  onRetry,
  compact = false,
}: ErrorStateProps) {
  if (compact) {
    return (
      <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
        <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
        <span className="text-sm text-red-400">{message}</span>
        {onRetry && (
          <button
            onClick={onRetry}
            className="ml-auto p-1 hover:bg-red-500/20 rounded transition-colors"
          >
            <RefreshCw className="w-3 h-3 text-red-400" />
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center mb-4">
        <AlertTriangle className="w-8 h-8 text-red-400" />
      </div>
      <h3 className="text-lg font-medium text-text-primary mb-1">{title}</h3>
      <p className="text-sm text-text-secondary mb-4 max-w-md">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-2 px-4 py-2 bg-card border border-border rounded-lg text-sm text-text-primary hover:border-accent/50 transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Try again
        </button>
      )}
    </div>
  )
}

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  message?: string
  action?: ReactNode
}

export function EmptyState({ icon, title, message, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      {icon && (
        <div className="w-16 h-16 rounded-full bg-accent/10 flex items-center justify-center mb-4 text-accent">
          {icon}
        </div>
      )}
      <h3 className="text-lg font-medium text-text-primary mb-1">{title}</h3>
      {message && <p className="text-sm text-text-secondary mb-4">{message}</p>}
      {action}
    </div>
  )
}
