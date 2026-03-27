/**
 * PaneContext — provides per-pane state and actions to descendant components.
 * Each PaneWorkspace wraps its children in a PaneProvider.
 * Components call usePaneContext() instead of global stores.
 */

import { createContext, useContext } from 'react'
import type { PaneState, EvoTab } from '../store/paneStore'
import type { SearchResponse, GeneNode } from '../types'
import type { EvolutionResponse } from '../types/evolution'
import { usePaneStore } from '../store/paneStore'

interface PaneContextValue {
  pane: PaneState
  // Search actions
  setQuery: (q: string) => void
  setResults: (r: SearchResponse | null) => void
  setIsLoading: (v: boolean) => void
  setError: (e: string | null) => void
  setSelectedGene: (g: GeneNode | null) => void
  openDrawer: () => void
  closeDrawer: () => void
  setSpeciesFilter: (f: string[] | null) => void
  // Evolution actions
  setEvoQuery: (q: string) => void
  setEvoData: (d: EvolutionResponse | null) => void
  setEvoLoading: (v: boolean) => void
  setEvoError: (e: string | null) => void
  setEvoTab: (t: EvoTab) => void
}

const PaneContext = createContext<PaneContextValue | null>(null)

export function PaneProvider({
  paneId,
  children,
}: {
  paneId: string
  children: React.ReactNode
}) {
  const { panes, updatePane } = usePaneStore()
  const pane = panes.find((p) => p.id === paneId)

  if (!pane) return null

  const update = (updates: Partial<PaneState>) => updatePane(paneId, updates)

  const value: PaneContextValue = {
    pane,
    setQuery: (query) => update({ query }),
    setResults: (results) => update({ results }),
    setIsLoading: (isLoading) => update({ isLoading }),
    setError: (error) => update({ error }),
    setSelectedGene: (selectedGene) => update({ selectedGene }),
    openDrawer: () => update({ isDrawerOpen: true }),
    closeDrawer: () => update({ isDrawerOpen: false, selectedGene: null }),
    setSpeciesFilter: (speciesFilter) => update({ speciesFilter }),
    setEvoQuery: (evoQuery) => update({ evoQuery }),
    setEvoData: (evoData) => update({ evoData }),
    setEvoLoading: (evoLoading) => update({ evoLoading }),
    setEvoError: (evoError) => update({ evoError }),
    setEvoTab: (evoTab) => update({ evoTab }),
  }

  return <PaneContext.Provider value={value}>{children}</PaneContext.Provider>
}

export function usePaneContext(): PaneContextValue {
  const ctx = useContext(PaneContext)
  if (!ctx) throw new Error('usePaneContext must be used inside a PaneProvider')
  return ctx
}
