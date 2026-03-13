/**
 * GraphControls — Overlay controls for the graph view.
 * Species legend + result count.
 */

import type { GeneNode } from '../../types'
import { SPECIES_COLORS, DEFAULT_NODE_COLOR } from './sigmaConfig'

interface GraphControlsProps {
  nodes: GeneNode[]
}

export function GraphControls({ nodes }: GraphControlsProps) {
  // Collect unique species from current results
  const speciesInView = new Map<string, { name: string; color: string; count: number }>()

  nodes.forEach((node) => {
    const taxon = node.species_taxon
    if (!speciesInView.has(taxon)) {
      speciesInView.set(taxon, {
        name: node.species_name || taxon,
        color: SPECIES_COLORS[taxon] ?? DEFAULT_NODE_COLOR,
        count: 0,
      })
    }
    speciesInView.get(taxon)!.count++
  })

  if (nodes.length === 0) return null

  return (
    <div className="absolute bottom-4 left-4 bg-gray-900/90 border border-gray-700 rounded-lg p-3 max-w-xs">
      <div className="text-xs text-gray-400 mb-2">
        {nodes.length} gene{nodes.length !== 1 ? 's' : ''} shown
      </div>
      <div className="space-y-1">
        {Array.from(speciesInView.entries()).map(([taxon, info]) => (
          <div key={taxon} className="flex items-center gap-2 text-xs">
            <span
              className="w-2.5 h-2.5 rounded-full flex-shrink-0"
              style={{ backgroundColor: info.color }}
            />
            <span className="text-gray-300 truncate">{info.name}</span>
            <span className="text-gray-500 ml-auto">{info.count}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
