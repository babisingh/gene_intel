/**
 * App — Root component for Gene-Intel Discovery Engine.
 *
 * Layout:
 *   - Top bar: logo + persona selector + ingestion status
 *   - Search area: SearchBar + Discovery Chips
 *   - Main: GraphView (full height, static on node click)
 *   - Right: AnalysisDrawer (opens on node click)
 *   - Error/empty state overlays
 */

import { useQuery } from '@tanstack/react-query'
import { useSearchStore } from './store/searchStore'
import { SearchBar } from './components/SearchBar/SearchBar'
import { GraphView } from './components/GraphView/GraphView'
import { GraphControls } from './components/GraphView/GraphControls'
import { AnalysisDrawer } from './components/AnalysisDrawer/AnalysisDrawer'
import { PersonaSelector } from './components/PersonaSelector'
import { IngestionStatus } from './components/IngestionStatus'
import { MarkdownText } from './components/MarkdownText'
import { api } from './api/client'

export default function App() {
  const { results, isLoading, error } = useSearchStore()
  const { data: speciesList } = useQuery({
    queryKey: ['species'],
    queryFn: api.species,
    staleTime: Infinity,
  })
  const speciesCount = speciesList?.length ?? 17

  const nodes = results?.nodes ?? []
  const edges = results?.edges ?? []

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col">
      {/* Top bar */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-gray-800 bg-gray-900">
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold text-blue-400 tracking-tight">Gene-Intel</span>
          <span className="text-xs text-gray-500 hidden sm:block">
            Discovery Engine — {speciesCount} species
          </span>
        </div>
        <div className="flex items-center gap-3">
          <IngestionStatus />
          <PersonaSelector />
        </div>
      </header>

      {/* Search area */}
      <div className="px-6 py-4 border-b border-gray-800 bg-gray-900/50">
        <SearchBar />
      </div>

      {/* Error banner */}
      {error && (
        <div className="mx-6 mt-4 px-4 py-3 bg-red-900/40 border border-red-700 rounded-lg text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Results explanation (non-researcher modes) */}
      {results?.explanation && (
        <div className="mx-6 mt-4 px-4 py-3 bg-blue-900/20 border border-blue-800/50 rounded-lg text-sm text-gray-300 leading-relaxed overflow-y-auto max-h-64">
          <MarkdownText>{results.explanation}</MarkdownText>
        </div>
      )}

      {/* Graph view */}
      <main className="flex-1 relative overflow-hidden">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-950/80 z-10">
            <div className="flex flex-col items-center gap-3">
              <svg className="animate-spin h-10 w-10 text-blue-400" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <span className="text-gray-400 text-sm">
                Searching {results === null ? `across ${speciesCount} species` : ''}…
              </span>
            </div>
          </div>
        )}

        <GraphView nodes={nodes} edges={edges} />
        <GraphControls nodes={nodes} />
      </main>

      {/* Analysis Drawer */}
      <AnalysisDrawer />
    </div>
  )
}
