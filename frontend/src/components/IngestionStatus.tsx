/**
 * IngestionStatus — Polling badge showing data ingestion state.
 * MVP: read-only. Ingestion runs via CLI only.
 */

import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

export function IngestionStatus() {
  const { data } = useQuery({
    queryKey: ['ingest-status'],
    queryFn: api.ingestStatus,
    refetchInterval: 5000,
  })

  if (!data || data.status === 'idle') return null

  const statusStyles: Record<string, string> = {
    running: 'bg-yellow-900/60 text-yellow-300 border-yellow-700',
    complete: 'bg-green-900/60 text-green-300 border-green-700',
    error: 'bg-red-900/60 text-red-300 border-red-700',
  }

  const style = statusStyles[data.status] ?? statusStyles.running

  return (
    <div className={`flex items-center gap-2 text-xs px-3 py-1.5 rounded-full border ${style}`}>
      {data.status === 'running' && (
        <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      )}
      <span>
        {data.status === 'running' && `Ingesting${data.species ? ` ${data.species}` : ''}…`}
        {data.status === 'complete' && 'Ingestion complete'}
        {data.status === 'error' && `Ingestion error: ${data.error}`}
      </span>
    </div>
  )
}
