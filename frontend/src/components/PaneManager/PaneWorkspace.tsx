/**
 * PaneWorkspace — one analysis pane. Renders either:
 *   mode='search'    → SearchBar + GraphView + AnalysisDrawer
 *   mode='evolution' → EvolutionPanel (phylo tree, domain ages, narrative, info)
 *
 * Wrapped in PaneProvider so all child hooks use this pane's state.
 */

import { PaneProvider, usePaneContext } from '../../contexts/PaneContext'
import { SearchBar } from '../SearchBar/SearchBar'
import { GraphView } from '../GraphView/GraphView'
import { GraphControls } from '../GraphView/GraphControls'
import { AnalysisDrawer } from '../AnalysisDrawer/AnalysisDrawer'
import { EvolutionPanel } from '../EvolutionView/EvolutionPanel'
import { usePaneStore } from '../../store/paneStore'
import type { PaneMode } from '../../store/paneStore'

function PaneInner({ paneId, onRemove, showClose }: {
  paneId: string
  onRemove: () => void
  showClose: boolean
}) {
  const { pane } = usePaneContext()
  const { updatePane } = usePaneStore()

  const setMode = (mode: PaneMode) => updatePane(paneId, { mode })

  const nodes = pane.results?.nodes ?? []
  const edges = pane.results?.edges ?? []

  return (
    <div className="flex flex-col h-full bg-gray-950 border border-gray-800 rounded-lg overflow-hidden">
      {/* Pane header */}
      <div className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-900 border-b border-gray-800 flex-shrink-0">
        {/* Mode toggle */}
        <div className="flex gap-0.5 bg-gray-800 rounded-md p-0.5">
          <button
            onClick={() => setMode('search')}
            className={`px-2.5 py-1 text-xs rounded font-medium transition-colors ${
              pane.mode === 'search'
                ? 'bg-blue-600 text-white'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            Graph Search
          </button>
          <button
            onClick={() => setMode('evolution')}
            className={`px-2.5 py-1 text-xs rounded font-medium transition-colors ${
              pane.mode === 'evolution'
                ? 'bg-emerald-700 text-white'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            Gene Evolution
          </button>
        </div>

        {/* Status */}
        {pane.mode === 'search' && pane.results && (
          <span className="text-xs text-gray-500 ml-1">
            {pane.results.result_count} gene{pane.results.result_count !== 1 ? 's' : ''}
          </span>
        )}

        <div className="flex-1" />

        {/* Close button */}
        {showClose && (
          <button
            onClick={onRemove}
            className="text-gray-600 hover:text-gray-300 transition-colors p-0.5"
            title="Close pane"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      {/* Content */}
      {pane.mode === 'search' ? (
        <>
          {/* Search bar */}
          <div className="px-3 py-2.5 border-b border-gray-800 bg-gray-900/50 flex-shrink-0">
            <SearchBar />
          </div>

          {/* Error banner */}
          {pane.error && (
            <div className="mx-3 mt-2 px-3 py-2 bg-red-900/40 border border-red-700 rounded text-xs text-red-300 flex-shrink-0">
              {pane.error}
            </div>
          )}

          {/* Graph view */}
          <div className="flex-1 relative overflow-hidden">
            {pane.isLoading && (
              <div className="absolute inset-0 flex items-center justify-center bg-gray-950/80 z-10">
                <div className="flex flex-col items-center gap-2">
                  <svg className="animate-spin h-7 w-7 text-blue-400" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  <span className="text-gray-400 text-xs">Searching…</span>
                </div>
              </div>
            )}
            <GraphView nodes={nodes} edges={edges} />
            <GraphControls nodes={nodes} />
            <AnalysisDrawer />
          </div>
        </>
      ) : (
        <div className="flex-1 overflow-hidden">
          <EvolutionPanel />
        </div>
      )}
    </div>
  )
}

export function PaneWorkspace({ paneId, onRemove, showClose }: {
  paneId: string
  onRemove: () => void
  showClose: boolean
}) {
  return (
    <PaneProvider paneId={paneId}>
      <PaneInner paneId={paneId} onRemove={onRemove} showClose={showClose} />
    </PaneProvider>
  )
}
