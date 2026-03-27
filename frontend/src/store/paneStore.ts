/**
 * Pane store — manages state for each independent analysis pane.
 * Up to MAX_PANES panes can be open simultaneously.
 */

import { create } from 'zustand'
import type { SearchResponse, GeneNode } from '../types'
import type { EvolutionResponse } from '../types/evolution'

export type PaneMode = 'search' | 'evolution'
export type EvoTab = 'tree' | 'domains' | 'narrative' | 'info'

export interface PaneState {
  id: string
  mode: PaneMode

  // Graph search state
  query: string
  results: SearchResponse | null
  isLoading: boolean
  error: string | null
  selectedGene: GeneNode | null
  isDrawerOpen: boolean
  speciesFilter: string[] | null

  // Evolution state
  evoQuery: string
  evoData: EvolutionResponse | null
  evoLoading: boolean
  evoError: string | null
  evoTab: EvoTab
}

export const MAX_PANES = 4

function makePane(id: string): PaneState {
  return {
    id,
    mode: 'search',
    query: '',
    results: null,
    isLoading: false,
    error: null,
    selectedGene: null,
    isDrawerOpen: false,
    speciesFilter: null,
    evoQuery: '',
    evoData: null,
    evoLoading: false,
    evoError: null,
    evoTab: 'tree',
  }
}

let _nextId = 1

interface PaneStoreState {
  panes: PaneState[]
  addPane: () => void
  removePane: (id: string) => void
  updatePane: (id: string, updates: Partial<PaneState>) => void
}

export const usePaneStore = create<PaneStoreState>((set) => ({
  panes: [makePane(String(_nextId++))],

  addPane: () =>
    set((s) => {
      if (s.panes.length >= MAX_PANES) return s
      return { panes: [...s.panes, makePane(String(_nextId++))] }
    }),

  removePane: (id) =>
    set((s) => {
      if (s.panes.length <= 1) return s  // always keep at least 1
      return { panes: s.panes.filter((p) => p.id !== id) }
    }),

  updatePane: (id, updates) =>
    set((s) => ({
      panes: s.panes.map((p) => (p.id === id ? { ...p, ...updates } : p)),
    })),
}))
