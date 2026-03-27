/**
 * Custom hook for fetching gene detail on drawer open.
 */

import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { usePaneContext } from '../contexts/PaneContext'

export function useGeneDetail() {
  const { pane } = usePaneContext()
  const { selectedGene } = pane

  return useQuery({
    queryKey: ['gene', selectedGene?.gene_id, 'researcher'],
    queryFn: () => api.gene(selectedGene!.gene_id, 'researcher'),
    enabled: selectedGene !== null,
    staleTime: 5 * 60 * 1000,
  })
}
