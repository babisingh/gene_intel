/**
 * GeneLocus — Custom SVG gene architecture diagram.
 *
 * Renders the Exon/UTR/CDS feature structure of a gene as a horizontal bar.
 * Features are drawn to scale relative to gene length.
 * Clicking a feature shows its properties in a tooltip.
 *
 * Visual encoding:
 *   Blue filled rect   = CDS exon
 *   Green filled rect  = UTR (5' or 3')
 *   Thin line          = intron
 *   Grey thin rect     = non-coding exon
 */

import { useState } from 'react'
import type { FeatureRecord, GeneNode } from '../../types'

interface TooltipState {
  feature: FeatureRecord
  x: number
  y: number
}

const SVG_WIDTH = 600
const SVG_HEIGHT = 60
const TRACK_Y = 30
const MIN_FEATURE_WIDTH = 3

function getFeatureColor(type: FeatureRecord['type']): string {
  switch (type) {
    case 'CDS': return '#3B82F6'        // blue
    case 'UTR': return '#10B981'        // green
    case 'exon': return '#9CA3AF'       // grey
    case 'start_codon': return '#F59E0B' // amber
    case 'stop_codon': return '#EF4444'  // red
    default: return '#6B7280'
  }
}

function getFeatureHeight(type: FeatureRecord['type']): number {
  switch (type) {
    case 'CDS': return 24
    case 'UTR': return 16
    default: return 20
  }
}

// TypeScript interface name fix - remove space
interface GeneLocusProps {
  gene: GeneNode
  features: FeatureRecord[]
}

export function GeneLocus({ gene, features }: GeneLocusProps) {
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)

  const geneLength = gene.end - gene.start
  if (geneLength <= 0 || features.length === 0) {
    return (
      <div className="text-gray-500 text-sm text-center py-4">
        No feature data available
      </div>
    )
  }

  const toSvgX = (genomicPos: number) =>
    ((genomicPos - gene.start) / geneLength) * SVG_WIDTH

  const featureWidth = (f: FeatureRecord) =>
    Math.max(MIN_FEATURE_WIDTH, (f.length / geneLength) * SVG_WIDTH)

  return (
    <div className="relative">
      <svg
        width="100%"
        viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
        className="overflow-visible"
        onMouseLeave={() => setTooltip(null)}
      >
        {/* Chromosome backbone */}
        <line
          x1={0}
          y1={TRACK_Y}
          x2={SVG_WIDTH}
          y2={TRACK_Y}
          stroke="#374151"
          strokeWidth={2}
        />

        {/* Gene direction arrow */}
        {gene.strand === '+' ? (
          <polygon
            points={`${SVG_WIDTH - 8},${TRACK_Y - 5} ${SVG_WIDTH},${TRACK_Y} ${SVG_WIDTH - 8},${TRACK_Y + 5}`}
            fill="#4B5563"
          />
        ) : (
          <polygon
            points={`8,${TRACK_Y - 5} 0,${TRACK_Y} 8,${TRACK_Y + 5}`}
            fill="#4B5563"
          />
        )}

        {/* Feature rectangles */}
        {features.map((f) => {
          const x = toSvgX(f.start)
          const w = featureWidth(f)
          const h = getFeatureHeight(f.type)
          const color = getFeatureColor(f.type)

          return (
            <rect
              key={f.feature_id}
              x={x}
              y={TRACK_Y - h / 2}
              width={w}
              height={h}
              fill={color}
              opacity={0.85}
              rx={2}
              className="cursor-pointer hover:opacity-100"
              onMouseEnter={(e) => {
                const rect = (e.currentTarget as SVGRectElement).getBoundingClientRect()
                setTooltip({ feature: f, x: rect.left, y: rect.top })
              }}
            />
          )
        })}
      </svg>

      {/* Feature tooltip */}
      {tooltip && (
        <div
          className="fixed z-50 bg-gray-900 border border-gray-700 rounded-lg p-2 text-xs shadow-xl pointer-events-none"
          style={{ left: tooltip.x + 4, top: tooltip.y - 60 }}
        >
          <div className="font-semibold text-white">{tooltip.feature.type}</div>
          <div className="text-gray-400">Rank: {tooltip.feature.rank}</div>
          <div className="text-gray-400">
            {tooltip.feature.start.toLocaleString()}–{tooltip.feature.end.toLocaleString()}
          </div>
          <div className="text-gray-400">{tooltip.feature.length.toLocaleString()} bp</div>
        </div>
      )}

      {/* Legend */}
      <div className="flex gap-3 mt-2 text-xs text-gray-500">
        {[
          { type: 'CDS', color: '#3B82F6', label: 'CDS' },
          { type: 'UTR', color: '#10B981', label: 'UTR' },
          { type: 'exon', color: '#9CA3AF', label: 'Exon' },
        ].map(({ color, label }) => (
          <div key={label} className="flex items-center gap-1">
            <span className="w-3 h-2 rounded-sm inline-block" style={{ backgroundColor: color }} />
            {label}
          </div>
        ))}
      </div>
    </div>
  )
}
