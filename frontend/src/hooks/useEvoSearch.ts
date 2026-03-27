/**
 * Hook for executing evolutionary gene family lookup within a pane.
 */

import { useCallback } from 'react'
import { api } from '../api/client'
import { usePaneContext } from '../contexts/PaneContext'

export function useEvoSearch() {
  const { setEvoData, setEvoLoading, setEvoError } = usePaneContext()

  const executeEvoSearch = useCallback(
    async (geneName: string) => {
      const name = geneName.trim()
      if (!name) return

      setEvoLoading(true)
      setEvoError(null)
      setEvoData(null)

      try {
        const data = await api.evolution(name)
        setEvoData(data)
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Evolution lookup failed'
        setEvoError(msg)
      } finally {
        setEvoLoading(false)
      }
    },
    [setEvoData, setEvoLoading, setEvoError],
  )

  return { executeEvoSearch }
}
