/**
 * Zustand store: UI state — drawer open/close, persona
 */

import { create } from 'zustand'

interface UiStore {
  isDrawerOpen: boolean
  openDrawer: () => void
  closeDrawer: () => void

  // Graph layout
  graphLayout: 'force' | 'circular'
  setGraphLayout: (layout: 'force' | 'circular') => void
}

export const useUiStore = create<UiStore>((set) => ({
  isDrawerOpen: false,
  openDrawer: () => set({ isDrawerOpen: true }),
  closeDrawer: () => set({ isDrawerOpen: false }),

  graphLayout: 'force',
  setGraphLayout: (graphLayout) => set({ graphLayout }),
}))
