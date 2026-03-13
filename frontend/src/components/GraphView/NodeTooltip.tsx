/**
 * NodeTooltip — Hover tooltip showing gene summary.
 * Rendered as a portal above the graph canvas.
 */

import type { GeneNode } from '../../types'
import { SPECIES_COLORS, DEFAULT_NODE_COLOR } from './sigmaConfig'

interface NodeTooltipProps {
  gene: GeneNode
  x: number
  y: number
}

export function NodeTooltip({ gene, x, y }: NodeTooltipProps) {
  const color = SPECIES_COLORS[gene.species_taxon] ?? DEFAULT_NODE_COLOR

  return (
    <div
      className="fixed z-50 bg-gray-900 border border-gray-700 rounded-lg p-3 shadow-xl text-xs pointer-events-none"
      style={{ left: x + 12, top: y - 8 }}
    >
      <div className="flex items-center gap-2 mb-1">
        <span
          className="w-2 h-2 rounded-full flex-shrink-0"
          style={{ backgroundColor: color }}
        />
        <span className="font-semibold text-white">{gene.name}</span>
      </div>
      <div className="text-gray-400 space-y-0.5">
        <div>{gene.species_name}</div>
        <div>chr{gene.chromosome}:{gene.start.toLocaleString()}–{gene.end.toLocaleString()}</div>
        {gene.cds_length && <div>CDS: {gene.cds_length.toLocaleString()} bp</div>}
        {gene.exon_count && <div>Exons: {gene.exon_count}</div>}
        {gene.domains.length > 0 && (
          <div className="text-blue-400 truncate max-w-48">
            {gene.domains.slice(0, 3).join(', ')}
            {gene.domains.length > 3 && ` +${gene.domains.length - 3}`}
          </div>
        )}
      </div>
      <div className="text-gray-600 mt-1">Click to open details</div>
    </div>
  )
}
