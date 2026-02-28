import { create } from 'zustand'

interface UIState {
  // Command palette
  commandPaletteOpen: boolean
  openCommandPalette: () => void
  closeCommandPalette: () => void
  toggleCommandPalette: () => void

  // Sidebar (mobile)
  sidebarOpen: boolean
  openSidebar: () => void
  closeSidebar: () => void
  toggleSidebar: () => void

  // Selected artifact for modal
  selectedArtifactId: string | null
  setSelectedArtifact: (id: string | null) => void

  // Graph filters
  graphFilters: {
    types: string[]
    timeRange: 'day' | 'week' | 'month' | 'all'
    searchQuery: string
  }
  setGraphFilters: (filters: Partial<UIState['graphFilters']>) => void

  // Notifications
  notifications: Notification[]
  addNotification: (notification: Omit<Notification, 'id'>) => void
  removeNotification: (id: string) => void
}

interface Notification {
  id: string
  type: 'info' | 'success' | 'warning' | 'error'
  title: string
  message?: string
  duration?: number
}

export const useUIStore = create<UIState>((set) => ({
  // Command palette
  commandPaletteOpen: false,
  openCommandPalette: () => set({ commandPaletteOpen: true }),
  closeCommandPalette: () => set({ commandPaletteOpen: false }),
  toggleCommandPalette: () => set((state) => ({ commandPaletteOpen: !state.commandPaletteOpen })),

  // Sidebar
  sidebarOpen: false,
  openSidebar: () => set({ sidebarOpen: true }),
  closeSidebar: () => set({ sidebarOpen: false }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),

  // Selected artifact
  selectedArtifactId: null,
  setSelectedArtifact: (id) => set({ selectedArtifactId: id }),

  // Graph filters
  graphFilters: {
    types: [],
    timeRange: 'all',
    searchQuery: '',
  },
  setGraphFilters: (filters) =>
    set((state) => ({
      graphFilters: { ...state.graphFilters, ...filters },
    })),

  // Notifications
  notifications: [],
  addNotification: (notification) =>
    set((state) => ({
      notifications: [
        ...state.notifications,
        { ...notification, id: Date.now().toString() },
      ],
    })),
  removeNotification: (id) =>
    set((state) => ({
      notifications: state.notifications.filter((n) => n.id !== id),
    })),
}))
