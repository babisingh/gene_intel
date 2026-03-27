/**
 * Zustand store: query, results, selected gene
 */

import { create } from 'zustand'
import type { SearchResponse, GeneNode, Persona } from '../types'

interface SearchStore {
  // Current query state
  query: string
  setQuery: (query: string) => void

  // Results
  results: SearchResponse | null
  setResults: (results: SearchResponse | null) => void

  // Selected gene (for Analysis Drawer)
  selectedGene: GeneNode | null
  setSelectedGene: (gene: GeneNode | null) => void

  // Loading state
  isLoading: boolean
  setIsLoading: (loading: boolean) => void

  // Error state
  error: string | null
  setError: (error: string | null) => void

  // Persona
  persona: Persona
  setPersona: (persona: Persona) => void

  // Species filter
  speciesFilter: string[] | null
  setSpeciesFilter: (filter: string[] | null) => void

  // Clear everything
  reset: () => void
}

export const useSearchStore = create<SearchStore>((set) => ({
  query: '',
  setQuery: (query) => set({ query }),

  results: null,
  setResults: (results) => set({ results }),

  selectedGene: null,
  setSelectedGene: (selectedGene) => set({ selectedGene }),

  isLoading: false,
  setIsLoading: (isLoading) => set({ isLoading }),

  error: null,
  setError: (error) => set({ error }),

  persona: 'researcher',
  setPersona: (persona) => set({ persona }),

  speciesFilter: null,
  setSpeciesFilter: (speciesFilter) => set({ speciesFilter }),

  reset: () =>
    set({
      query: '',
      results: null,
      selectedGene: null,
      isLoading: false,
      error: null,
    }),
}))
