/// <reference types="vite/client" />
/**
 * Typed fetch wrapper for the Gene-Intel API.
 * All API calls go through this module for consistent error handling and base URL.
 */

import type {
  SearchRequest,
  SearchResponse,
  SpeciesInfo,
  GeneDetailResponse,
  NeighborhoodResponse,
  HealthResponse,
  IngestStatusResponse,
} from '../types'
import type { EvolutionResponse } from '../types/evolution'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`API ${response.status}: ${errorText}`)
  }

  return response.json() as Promise<T>
}

// ── Endpoints ────────────────────────────────────────────────────────────────

export const api = {
  search: (request: SearchRequest): Promise<SearchResponse> =>
    apiFetch('/api/search', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  species: (): Promise<SpeciesInfo[]> =>
    apiFetch('/api/species'),

  gene: (geneId: string, persona = 'student'): Promise<GeneDetailResponse> =>
    apiFetch(`/api/gene/${encodeURIComponent(geneId)}?persona=${persona}`),

  neighborhood: (
    geneId: string,
    maxDistanceBp = 10000,
    limit = 50,
  ): Promise<NeighborhoodResponse> =>
    apiFetch(
      `/api/neighborhood/${encodeURIComponent(geneId)}?max_distance_bp=${maxDistanceBp}&limit=${limit}`,
    ),

  health: (): Promise<HealthResponse> =>
    apiFetch('/api/health'),

  ingestStatus: (): Promise<IngestStatusResponse> =>
    apiFetch('/api/ingest/status'),

  evolution: (geneName: string): Promise<EvolutionResponse> =>
    apiFetch(`/api/evolution/${encodeURIComponent(geneName)}`),
}
