/**
 * AnalysisDrawer — Side panel that opens when a gene node is clicked.
 *
 * Shows:
 *   - Gene metadata (name, coordinates, biotype)
 *   - GeneLocus SVG diagram
 *   - Domain badges
 *   - Agent C explanation (persona-aware)
 *   - Researcher: Cypher query used
 *
 * Graph stays static when drawer is open (Option B from spec).
 */

import { useUiStore } from '../../store/uiStore'
import { useSearchStore } from '../../store/searchStore'
import { useGeneDetail } from '../../hooks/useGeneDetail'
import { GeneLocus } from './GeneLocus'
import { DomainBadges } from './DomainBadges'
import { ExplainerCard } from './ExplainerCard'

export function AnalysisDrawer() {
  const isOpen = useUiStore((s) => s.isDrawerOpen)
  const closeDrawer = useUiStore((s) => s.closeDrawer)
  const selectedGene = useSearchStore((s) => s.selectedGene)
  const persona = useSearchStore((s) => s.persona)
  const results = useSearchStore((s) => s.results)

  const { data: detail, isLoading } = useGeneDetail()

  if (!isOpen || !selectedGene) return null

  const gene = detail?.gene ?? selectedGene
  const features = detail?.features ?? []

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 z-30"
        onClick={closeDrawer}
      />

      {/* Drawer panel */}
      <div className="fixed right-0 top-0 h-full w-[480px] max-w-full bg-gray-900 border-l border-gray-700 z-40 overflow-y-auto shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700 sticky top-0 bg-gray-900">
          <div>
            <h2 className="text-lg font-semibold text-white">{gene.name}</h2>
            <p className="text-sm text-gray-400">{gene.species_name}</p>
          </div>
          <button
            onClick={closeDrawer}
            className="text-gray-500 hover:text-white transition-colors p-1"
            aria-label="Close"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-6">
          {/* Gene metadata */}
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <span className="text-gray-500">Gene ID</span>
              <p className="text-white font-mono text-xs mt-0.5">{gene.gene_id}</p>
            </div>
            <div>
              <span className="text-gray-500">Biotype</span>
              <p className="text-white mt-0.5">{gene.biotype}</p>
            </div>
            <div>
              <span className="text-gray-500">Location</span>
              <p className="text-white mt-0.5 text-xs">
                chr{gene.chromosome}:{gene.start.toLocaleString()}–{gene.end.toLocaleString()}
                {' '}({gene.strand || '?'})
              </p>
            </div>
            <div>
              <span className="text-gray-500">CDS length</span>
              <p className="text-white mt-0.5">{gene.cds_length?.toLocaleString() ?? 'N/A'} bp</p>
            </div>
            {gene.exon_count != null && (
              <div>
                <span className="text-gray-500">Exons</span>
                <p className="text-white mt-0.5">{gene.exon_count}</p>
              </div>
            )}
            {gene.utr_cds_ratio != null && (
              <div>
                <span className="text-gray-500">UTR/CDS ratio</span>
                <p className="text-white mt-0.5">{gene.utr_cds_ratio.toFixed(3)}</p>
              </div>
            )}
          </div>

          {/* Gene locus diagram */}
          {isLoading ? (
            <div className="h-16 bg-gray-800 rounded animate-pulse" />
          ) : features.length > 0 ? (
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-2">Gene Architecture</h3>
              <GeneLocus gene={gene} features={features} />
            </div>
          ) : null}

          {/* Domains */}
          <div>
            <h3 className="text-sm font-medium text-gray-400 mb-2">Protein Domains</h3>
            <DomainBadges domains={gene.domains} />
          </div>

          {/* Agent C Explanation */}
          {isLoading ? (
            <div className="space-y-2">
              <div className="h-4 bg-gray-800 rounded animate-pulse w-3/4" />
              <div className="h-4 bg-gray-800 rounded animate-pulse" />
              <div className="h-4 bg-gray-800 rounded animate-pulse w-5/6" />
            </div>
          ) : detail?.explanation ? (
            <ExplainerCard
              explanation={detail.explanation}
              persona={persona}
              cypherUsed={results?.cypher_used}
            />
          ) : null}

          {/* Researcher: CSV export hint */}
          {persona === 'researcher' && (
            <div className="pt-2 border-t border-gray-700">
              <p className="text-xs text-gray-500">
                Export results: copy the Cypher query above and run it in the Neo4j Browser
                with <code className="text-green-400">:export csv</code>
              </p>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
