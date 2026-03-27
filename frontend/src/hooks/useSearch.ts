/**
 * Custom hook for executing a gene search query within a pane.
 */

import { useCallback } from 'react'
import { api } from '../api/client'
import { usePaneContext } from '../contexts/PaneContext'

export function useSearch() {
  const { pane, setResults, setIsLoading, setError } = usePaneContext()

  const executeSearch = useCallback(
    async (overrideQuery?: string) => {
      const q = overrideQuery ?? pane.query
      if (!q.trim()) return

      setIsLoading(true)
      setError(null)
      setResults(null)

      try {
        const results = await api.search({
          query: q,
          persona: 'researcher',
          species_filter: pane.speciesFilter,
          limit: 300,
        })
        setResults(results)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Search failed')
      } finally {
        setIsLoading(false)
      }
    },
    [pane.query, pane.speciesFilter, setResults, setIsLoading, setError],
  )

  return { executeSearch }
}
