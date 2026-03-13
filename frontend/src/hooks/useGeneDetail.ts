/**
 * Custom hook for fetching gene detail on drawer open.
 */

import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { useSearchStore } from '../store/searchStore'

export function useGeneDetail() {
  const { selectedGene, persona } = useSearchStore()

  return useQuery({
    queryKey: ['gene', selectedGene?.gene_id, persona],
    queryFn: () => api.gene(selectedGene!.gene_id, persona),
    enabled: selectedGene !== null,
    staleTime: 5 * 60 * 1000,  // 5 minutes
  })
}
