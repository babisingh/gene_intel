/**
 * Custom hook for fetching gene neighborhood.
 */

import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

export function useNeighborhood(geneId: string | null, maxDistanceBp = 10000) {
  return useQuery({
    queryKey: ['neighborhood', geneId, maxDistanceBp],
    queryFn: () => api.neighborhood(geneId!, maxDistanceBp),
    enabled: geneId !== null,
    staleTime: 5 * 60 * 1000,
  })
}
