/**
 * Custom hook for executing a gene search query.
 */

import { useCallback } from 'react'
import { api } from '../api/client'
import { useSearchStore } from '../store/searchStore'

export function useSearch() {
  const {
    query,
    persona,
    speciesFilter,
    setResults,
    setIsLoading,
    setError,
  } = useSearchStore()

  const executeSearch = useCallback(
    async (overrideQuery?: string) => {
      const q = overrideQuery ?? query
      if (!q.trim()) return

      setIsLoading(true)
      setError(null)
      setResults(null)

      try {
        const results = await api.search({
          query: q,
          persona,
          species_filter: speciesFilter,
          limit: 300,
        })
        setResults(results)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Search failed')
      } finally {
        setIsLoading(false)
      }
    },
    [query, persona, speciesFilter, setResults, setIsLoading, setError],
  )

  return { executeSearch }
}
