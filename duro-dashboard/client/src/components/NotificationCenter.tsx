import { useState, useEffect } from 'react'
import { Bell, X, Zap, Brain, CheckCircle, AlertTriangle } from 'lucide-react'
import { useActivity } from '@/hooks/useActivity'

interface Notification {
  id: string
  type: 'artifact' | 'system' | 'alert'
  title: string
  message?: string
  timestamp: string
  read: boolean
}

export default function NotificationCenter() {
  const [isOpen, setIsOpen] = useState(false)
  const [notifications, setNotifications] = useState<Notification[]>([])
  const { status, events } = useActivity()

  // Convert activity events to notifications
  useEffect(() => {
    if (events.length > 0) {
      const newNotifications = events.slice(0, 10).map((event) => ({
        id: event.id,
        type: 'artifact' as const,
        title: `New ${event.type}`,
        message: event.title || event.id,
        timestamp: event.created_at,
        read: false,
      }))
      setNotifications(newNotifications)
    }
  }, [events])

  const unreadCount = notifications.filter((n) => !n.read).length

  const markAllRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })))
  }

  const clearAll = () => {
    setNotifications([])
  }

  const getIcon = (type: string) => {
    switch (type) {
      case 'artifact':
        return <Brain className="w-4 h-4 text-accent" />
      case 'system':
        return <Zap className="w-4 h-4 text-warning" />
      case 'alert':
        return <AlertTriangle className="w-4 h-4 text-error" />
      default:
        return <Bell className="w-4 h-4 text-text-secondary" />
    }
  }

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(diff / 3600000)

    if (minutes < 1) return 'just now'
    if (minutes < 60) return `${minutes}m ago`
    if (hours < 24) return `${hours}h ago`
    return date.toLocaleDateString()
  }

  return (
    <div className="relative">
      {/* Bell button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 hover:bg-white/5 rounded transition-colors"
      >
        <Bell className="w-5 h-5 text-text-secondary" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-error text-white text-[10px] font-bold rounded-full flex items-center justify-center animate-pulse-dot">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
        {status === 'connected' && (
          <span className="absolute bottom-1 right-1 w-2 h-2 bg-success rounded-full" />
        )}
      </button>

      {/* Dropdown */}
      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />

          {/* Panel */}
          <div className="absolute right-0 top-full mt-2 w-80 bg-card border border-border rounded-lg shadow-xl z-50 overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between p-3 border-b border-border">
              <div className="flex items-center gap-2">
                <span className="font-medium text-sm">Notifications</span>
                {status === 'connected' && (
                  <span className="px-1.5 py-0.5 text-[10px] bg-success/20 text-success rounded">
                    LIVE
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1">
                {notifications.length > 0 && (
                  <>
                    <button
                      onClick={markAllRead}
                      className="p-1 text-xs text-text-secondary hover:text-text-primary"
                    >
                      <CheckCircle className="w-4 h-4" />
                    </button>
                    <button
                      onClick={clearAll}
                      className="p-1 text-xs text-text-secondary hover:text-text-primary"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* Notifications list */}
            <div className="max-h-80 overflow-y-auto">
              {notifications.length === 0 ? (
                <div className="p-6 text-center text-text-secondary text-sm">
                  No notifications
                </div>
              ) : (
                notifications.map((notification) => (
                  <div
                    key={notification.id}
                    className={`flex items-start gap-3 p-3 border-b border-border/50 hover:bg-white/5 transition-colors ${
                      !notification.read ? 'bg-accent/5' : ''
                    }`}
                  >
                    {getIcon(notification.type)}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-text-primary truncate">
                        {notification.title}
                      </p>
                      {notification.message && (
                        <p className="text-xs text-text-secondary truncate">
                          {notification.message}
                        </p>
                      )}
                      <p className="text-[10px] text-text-secondary mt-0.5">
                        {formatTime(notification.timestamp)}
                      </p>
                    </div>
                    {!notification.read && (
                      <span className="w-2 h-2 bg-accent rounded-full flex-shrink-0 mt-1" />
                    )}
                  </div>
                ))
              )}
            </div>

            {/* Footer */}
            {notifications.length > 0 && (
              <div className="p-2 border-t border-border">
                <button
                  onClick={() => setIsOpen(false)}
                  className="w-full py-1.5 text-xs text-center text-accent hover:text-accent/80 transition-colors"
                >
                  View Activity →
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
