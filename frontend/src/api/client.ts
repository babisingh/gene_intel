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

const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

/**
 * FastAPI sends errors as {"detail": "..."}. Show that text, not the raw JSON;
 * anything else (request validation lists, a proxy's error page) is shown as it came.
 */
function errorDetail(body: string): string {
  try {
    const detail = (JSON.parse(body) as { detail?: unknown } | null)?.detail
    if (typeof detail === 'string') return detail
  } catch {
    // Not JSON: fall through to the raw body.
  }
  return body
}

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
    throw new Error(`API ${response.status}: ${errorDetail(errorText)}`)
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
}
