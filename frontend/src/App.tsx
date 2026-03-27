/**
 * App — Multi-pane analysis workspace.
 *
 * Layout:
 *   - Top bar: logo + species count + add-pane button + ingestion status
 *   - Grid area: 1–4 independent PaneWorkspace instances
 *
 * Each pane can run Graph Search (NL → gene graph) or Gene Evolution
 * (gene symbol → phylo tree + domain ages + LLM narrative) independently.
 * Hard limit: 4 panes to stay within browser RAM budgets.
 */

import { useQuery } from '@tanstack/react-query'
import { usePaneStore, MAX_PANES } from './store/paneStore'
import { PaneWorkspace } from './components/PaneManager/PaneWorkspace'
import { IngestionStatus } from './components/IngestionStatus'
import { PersonaSelector } from './components/PersonaSelector'
import { api } from './api/client'

export default function App() {
  const { panes, addPane, removePane } = usePaneStore()
  const { data: speciesList } = useQuery({
    queryKey: ['species'],
    queryFn: api.species,
    staleTime: Infinity,
  })
  const speciesCount = speciesList?.length ?? 17

  // Grid layout: 1 pane = full, 2 = side-by-side, 3-4 = 2×2
  const gridClass =
    panes.length === 1
      ? 'grid-cols-1 grid-rows-1'
      : panes.length === 2
      ? 'grid-cols-2 grid-rows-1'
      : 'grid-cols-2 grid-rows-2'

  return (
    <div className="h-screen bg-gray-950 text-white flex flex-col overflow-hidden">
      {/* Top bar */}
      <header className="flex items-center justify-between px-4 py-2 border-b border-gray-800 bg-gray-900 flex-shrink-0">
        <div className="flex items-center gap-3">
          <span className="text-base font-bold text-blue-400 tracking-tight">Gene-Intel</span>
          <span className="text-xs text-gray-500 hidden sm:block">
            Discovery Engine · {speciesCount} species · 3.5 billion years
          </span>
        </div>

        <div className="flex items-center gap-2">
          <IngestionStatus />
          <PersonaSelector />

          {/* Add pane button */}
          {panes.length < MAX_PANES && (
            <button
              onClick={addPane}
              title="Open new analysis pane"
              className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 hover:bg-gray-700
                text-gray-300 hover:text-white text-xs rounded-lg border border-gray-700
                transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Add pane
              <span className="text-gray-600">{panes.length}/{MAX_PANES}</span>
            </button>
          )}
        </div>
      </header>

      {/* Pane grid */}
      <main className={`flex-1 grid ${gridClass} gap-1.5 p-1.5 overflow-hidden`}>
        {panes.map((pane) => (
          <PaneWorkspace
            key={pane.id}
            paneId={pane.id}
            onRemove={() => removePane(pane.id)}
            showClose={panes.length > 1}
          />
        ))}
      </main>
    </div>
  )
}
