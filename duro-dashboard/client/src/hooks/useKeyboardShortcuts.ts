import { useEffect, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'

const ROUTES = [
  '/overview',
  '/search',
  '/memory',
  '/activity',
  '/reviews',
  '/episodes',
  '/skills',
  '/incidents',
  '/insights',
  '/relationships',
  '/settings',
]

interface UseKeyboardShortcutsOptions {
  onOpenSearch?: () => void
  onEscape?: () => void
}

export function useKeyboardShortcuts(options: UseKeyboardShortcutsOptions = {}) {
  const navigate = useNavigate()
  const location = useLocation()

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      // Ignore if typing in an input/textarea
      const target = e.target as HTMLElement
      if (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.isContentEditable
      ) {
        // Allow Escape in inputs
        if (e.key === 'Escape' && options.onEscape) {
          options.onEscape()
        }
        return
      }

      // Global shortcuts
      switch (e.key) {
        case '/':
          e.preventDefault()
          if (options.onOpenSearch) {
            options.onOpenSearch()
          } else {
            navigate('/search')
          }
          break

        case 'Escape':
          if (options.onEscape) {
            options.onEscape()
          }
          break

        case 'j':
        case 'ArrowDown':
          if (!e.metaKey && !e.ctrlKey) {
            e.preventDefault()
            const currentIndex = ROUTES.indexOf(location.pathname)
            if (currentIndex < ROUTES.length - 1) {
              navigate(ROUTES[currentIndex + 1])
            }
          }
          break

        case 'k':
        case 'ArrowUp':
          if (!e.metaKey && !e.ctrlKey) {
            e.preventDefault()
            const currentIndex = ROUTES.indexOf(location.pathname)
            if (currentIndex > 0) {
              navigate(ROUTES[currentIndex - 1])
            }
          }
          break

        case 'g':
          // g+h = home (overview)
          break

        case '?':
          // Show help modal (future)
          break
      }
    },
    [navigate, location.pathname, options]
  )

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])
}
