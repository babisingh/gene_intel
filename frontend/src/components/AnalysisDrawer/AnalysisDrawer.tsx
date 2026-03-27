/**
 * AnalysisDrawer — pane-local side panel opened when a gene node is clicked.
 * Positioned absolute within the pane (not full-screen fixed).
 */

import { usePaneContext } from '../../contexts/PaneContext'
import { useGeneDetail } from '../../hooks/useGeneDetail'
import { GeneLocus } from './GeneLocus'
import { DomainBadges } from './DomainBadges'
import { ExplainerCard } from './ExplainerCard'

export function AnalysisDrawer() {
  const { pane, closeDrawer } = usePaneContext()
  const { isDrawerOpen, selectedGene, results } = pane
  const { data: detail, isLoading } = useGeneDetail()

  if (!isDrawerOpen || !selectedGene) return null

  const gene = detail?.gene ?? selectedGene
  const features = detail?.features ?? []

  return (
    <>
      {/* Backdrop within pane */}
      <div className="absolute inset-0 bg-black/40 z-30" onClick={closeDrawer} />

      {/* Drawer panel */}
      <div className="absolute right-0 top-0 h-full w-[420px] max-w-full bg-gray-900 border-l border-gray-700 z-40 overflow-y-auto shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-3 border-b border-gray-700 sticky top-0 bg-gray-900">
          <div>
            <h2 className="text-base font-semibold text-white">{gene.name}</h2>
            <p className="text-xs text-gray-400">{gene.species_name}</p>
          </div>
          <button
            onClick={closeDrawer}
            className="text-gray-500 hover:text-white transition-colors p-1"
            aria-label="Close"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-3 space-y-4">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <span className="text-gray-500">Gene ID</span>
              <p className="text-white font-mono mt-0.5 truncate">{gene.gene_id}</p>
            </div>
            <div>
              <span className="text-gray-500">Biotype</span>
              <p className="text-white mt-0.5">{gene.biotype}</p>
            </div>
            <div>
              <span className="text-gray-500">Location</span>
              <p className="text-white mt-0.5">
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
                <span className="text-gray-500">UTR/CDS</span>
                <p className="text-white mt-0.5">{gene.utr_cds_ratio.toFixed(3)}</p>
              </div>
            )}
          </div>

          {isLoading ? (
            <div className="h-12 bg-gray-800 rounded animate-pulse" />
          ) : features.length > 0 ? (
            <div>
              <h3 className="text-xs font-medium text-gray-400 mb-1.5">Gene Architecture</h3>
              <GeneLocus gene={gene} features={features} />
            </div>
          ) : null}

          <div>
            <h3 className="text-xs font-medium text-gray-400 mb-1.5">Protein Domains</h3>
            <DomainBadges domains={gene.domains} />
          </div>

          {isLoading ? (
            <div className="space-y-1.5">
              <div className="h-3 bg-gray-800 rounded animate-pulse w-3/4" />
              <div className="h-3 bg-gray-800 rounded animate-pulse" />
              <div className="h-3 bg-gray-800 rounded animate-pulse w-5/6" />
            </div>
          ) : detail?.explanation ? (
            <ExplainerCard
              explanation={detail.explanation}
              persona="researcher"
              cypherUsed={results?.cypher_used}
            />
          ) : null}

          <div className="pt-2 border-t border-gray-700">
            <p className="text-xs text-gray-500">
              Export: copy Cypher query above → run in Neo4j Browser with{' '}
              <code className="text-green-400">:export csv</code>
            </p>
          </div>
        </div>
      </div>
    </>
  )
}
