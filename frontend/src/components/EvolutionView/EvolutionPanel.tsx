/**
 * EvolutionPanel — container for the evolutionary analysis view.
 *
 * Tabs:
 *   Tree      → PhyloTreeView SVG with domain gain/loss overlays
 *   Domains   → DomainPresenceMatrix (species × domain presence grid)
 *   Narrative → LLM evolutionary story
 *   Info      → Raw data / calculations / methodology
 */

import { useState } from 'react'
import { usePaneContext } from '../../contexts/PaneContext'
import { useEvoSearch } from '../../hooks/useEvoSearch'
import { PhyloTreeView } from './PhyloTreeView'
import { DomainPresenceMatrix } from './DomainAgeChart'
import { NarrativeCard } from './NarrativeCard'
import { InfoPanel } from './InfoPanel'
import type { EvoTab } from '../../store/paneStore'

// Example gene names known to exist across multiple species
const EVO_CHIPS = [
  { label: 'TP53',   desc: 'Tumor suppressor · metazoans' },
  { label: 'GAPDH',  desc: 'Metabolic enzyme · near-universal' },
  { label: 'SOD1',   desc: 'Antioxidant · bacteria to human' },
  { label: 'BRCA1',  desc: 'DNA repair · vertebrates' },
  { label: 'ACTB',   desc: 'Beta-actin · eukaryotes' },
  { label: 'EGFR',   desc: 'Receptor kinase · metazoans' },
  { label: 'MYC',    desc: 'Oncogene · metazoans' },
  { label: 'PCNA',   desc: 'DNA clamp · eukaryotes' },
]

const TABS: { id: EvoTab; label: string }[] = [
  { id: 'tree',      label: 'Phylo Tree' },
  { id: 'domains',   label: 'Domain Ages' },
  { id: 'narrative', label: 'Narrative' },
  { id: 'info',      label: 'Data & Info' },
]

export function EvolutionPanel() {
  const { pane, setEvoQuery, setEvoTab } = usePaneContext()
  const { executeEvoSearch } = useEvoSearch()
  const [inputValue, setInputValue] = useState(pane.evoQuery)
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null)

  const { evoData, evoLoading, evoError, evoTab } = pane

  const handleSearch = (name: string) => {
    const trimmed = name.trim().toUpperCase()
    if (!trimmed) return
    setInputValue(trimmed)
    setEvoQuery(trimmed)
    setSelectedDomain(null)
    executeEvoSearch(trimmed)
  }

  const presentTaxons = new Set(
    (evoData?.species_profiles ?? []).map((p) => p.taxon_id)
  )

  return (
    <div className="flex flex-col h-full">
      {/* Search row */}
      <div className="px-3 py-2.5 border-b border-gray-800 bg-gray-900/60">
        <form
          className="flex gap-2"
          onSubmit={(e) => { e.preventDefault(); handleSearch(inputValue) }}
        >
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Gene symbol — e.g. TP53, BRCA1, GAPDH, SOD1, EGFR"
            className="
              flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5
              text-sm text-white placeholder-gray-500
              focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500
              disabled:opacity-50
            "
            disabled={evoLoading}
          />
          <button
            type="submit"
            disabled={evoLoading || !inputValue.trim()}
            className="
              px-4 py-1.5 bg-emerald-700 hover:bg-emerald-600 disabled:bg-gray-700
              text-white text-sm font-medium rounded-lg transition-colors
              disabled:cursor-not-allowed whitespace-nowrap
            "
          >
            {evoLoading ? (
              <span className="flex items-center gap-1.5">
                <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Analysing…
              </span>
            ) : (
              'Analyse'
            )}
          </button>
        </form>

        {/* Example chips */}
        <div className="flex flex-wrap gap-1.5 mt-2">
          {EVO_CHIPS.map((chip) => (
            <button
              key={chip.label}
              onClick={() => handleSearch(chip.label)}
              title={chip.desc}
              className="px-2 py-0.5 rounded-full text-xs bg-emerald-900/40 text-emerald-300
                border border-emerald-800/60 hover:bg-emerald-800/50 transition-colors"
            >
              {chip.label}
            </button>
          ))}
        </div>
      </div>

      {/* Error */}
      {evoError && (
        <div className="mx-3 mt-2 px-3 py-2 bg-red-900/40 border border-red-700 rounded text-xs text-red-300">
          {evoError}
        </div>
      )}

      {/* Empty state */}
      {!evoData && !evoLoading && !evoError && (
        <div className="flex-1 flex items-center justify-center text-center px-8">
          <div className="space-y-2">
            <div className="text-3xl text-gray-700">🧬</div>
            <p className="text-sm text-gray-500">
              Enter a gene symbol to trace its evolutionary history across{' '}
              <span className="text-gray-400">17 species spanning 3.5 billion years</span>.
            </p>
            <p className="text-xs text-gray-600">
              Reveals domain gain/loss events, regulatory complexity trajectories, and
              an AI-generated evolutionary narrative.
            </p>
          </div>
        </div>
      )}

      {/* Loading state */}
      {evoLoading && (
        <div className="flex-1 flex items-center justify-center">
          <div className="space-y-3 text-center">
            <svg className="animate-spin h-8 w-8 text-emerald-400 mx-auto" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <div className="text-sm text-gray-400">Querying {pane.evoQuery} across 17 species…</div>
            <div className="text-xs text-gray-600">Running Dollo parsimony · generating narrative</div>
          </div>
        </div>
      )}

      {/* Results */}
      {evoData && !evoLoading && (
        <>
          {/* Results header */}
          <div className="px-3 py-2 border-b border-gray-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-white">{evoData.gene_name}</span>
              <span className="text-xs text-gray-500">
                found in {evoData.species_count}/17 species
              </span>
              {selectedDomain && (
                <span className="text-xs bg-blue-900/50 text-blue-300 px-2 py-0.5 rounded-full border border-blue-800">
                  filtering: {selectedDomain}
                  <button
                    className="ml-1.5 text-blue-400 hover:text-white"
                    onClick={() => setSelectedDomain(null)}
                  >×</button>
                </span>
              )}
            </div>
            <div className="text-xs text-gray-600">
              {evoData.domain_ages.length} domains · {evoData.domain_events.filter(e => e.type === 'gain').length} gains · {evoData.domain_events.filter(e => e.type === 'loss').length} losses
            </div>
          </div>

          {/* Tab bar */}
          <div className="flex border-b border-gray-800 bg-gray-900/40 px-1">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setEvoTab(tab.id)}
                className={`
                  px-4 py-2 text-xs font-medium transition-colors border-b-2
                  ${evoTab === tab.id
                    ? 'border-emerald-500 text-emerald-300'
                    : 'border-transparent text-gray-500 hover:text-gray-300'}
                `}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="flex-1 overflow-auto">
            {evoTab === 'tree' && (
              <div className="p-3 h-full">
                <PhyloTreeView
                  tree={evoData.phylo_tree}
                  speciesMeta={evoData.species_meta}
                  presentTaxons={presentTaxons}
                  domainEvents={evoData.domain_events}
                  selectedDomain={selectedDomain}
                />
              </div>
            )}
            {evoTab === 'domains' && (
              <div className="p-3 overflow-auto">
                <DomainPresenceMatrix
                  domainAges={evoData.domain_ages}
                  speciesMeta={evoData.species_meta}
                  selectedDomain={selectedDomain}
                  onDomainSelect={setSelectedDomain}
                />
              </div>
            )}
            {evoTab === 'narrative' && (
              <NarrativeCard
                narrative={evoData.narrative}
                geneName={evoData.gene_name}
                isLoading={false}
              />
            )}
            {evoTab === 'info' && <InfoPanel data={evoData} />}
          </div>
        </>
      )}
    </div>
  )
}
