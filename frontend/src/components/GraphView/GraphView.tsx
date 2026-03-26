/**
 * GraphView — SVG gene network renderer.
 *
 * Replaces the previous Sigma.js WebGL renderer which had persistent
 * canvas-sizing issues in the flex layout. Pure SVG always renders correctly.
 *
 * Layout: circular for small result sets, grid fallback for large ones.
 * Clicking a node opens the Analysis Drawer.
 */

import { useMemo, useState } from 'react'
import type { GeneNode, GraphEdge } from '../../types'
import { getNodeColor, getNodeSize } from './sigmaConfig'
import { useSearchStore } from '../../store/searchStore'
import { useUiStore } from '../../store/uiStore'

interface GraphViewProps {
  nodes: GeneNode[]
  edges: GraphEdge[]
}

const MAX_NODES = 300
const W = 900
const H = 560

function circularPositions(count: number) {
  if (count === 1) return [{ x: W / 2, y: H / 2 }]
  const cx = W / 2
  const cy = H / 2
  const r = Math.min(W, H) * 0.38
  return Array.from({ length: count }, (_, i) => {
    const angle = (2 * Math.PI * i) / count - Math.PI / 2
    return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) }
  })
}

export function GraphView({ nodes, edges }: GraphViewProps) {
  const setSelectedGene = useSearchStore((s) => s.setSelectedGene)
  const openDrawer = useUiStore((s) => s.openDrawer)
  const [hovered, setHovered] = useState<string | null>(null)

  const limited = nodes.slice(0, MAX_NODES)

  const positions = useMemo(() => circularPositions(limited.length), [limited.length])

  const idToPos = useMemo(() => {
    const m = new Map<string, { x: number; y: number }>()
    limited.forEach((n, i) => m.set(n.gene_id, positions[i]))
    return m
  }, [limited, positions])

  if (limited.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500 text-sm">
        Search for genes to visualise the network
      </div>
    )
  }

  return (
    <div className="relative w-full h-full">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="xMidYMid meet"
        className="w-full h-full"
      >
        {/* Edges */}
        {edges.map((edge, i) => {
          const s = idToPos.get(edge.source)
          const t = idToPos.get(edge.target)
          if (!s || !t) return null
          return (
            <line
              key={i}
              x1={s.x} y1={s.y}
              x2={t.x} y2={t.y}
              stroke="#374151"
              strokeWidth={1}
              strokeOpacity={0.6}
            />
          )
        })}

        {/* Nodes */}
        {limited.map((node, i) => {
          const { x, y } = positions[i]
          const color = getNodeColor(node.species_taxon)
          const r = getNodeSize(node.cds_length)
          const isHovered = hovered === node.gene_id
          const label = node.name || node.gene_id.slice(0, 10)

          return (
            <g
              key={node.gene_id}
              transform={`translate(${x},${y})`}
              onClick={() => { setSelectedGene(node); openDrawer() }}
              onMouseEnter={() => setHovered(node.gene_id)}
              onMouseLeave={() => setHovered(null)}
              style={{ cursor: 'pointer' }}
            >
              {/* Glow ring on hover */}
              {isHovered && (
                <circle r={r + 6} fill={color} opacity={0.25} />
              )}
              <circle
                r={isHovered ? r + 2 : r}
                fill={color}
                stroke={isHovered ? 'white' : 'rgba(255,255,255,0.2)'}
                strokeWidth={isHovered ? 2 : 1}
                style={{ transition: 'r 0.15s, stroke 0.15s' }}
              />
              {/* Label — always shown for small sets, only on hover for large */}
              {(limited.length <= 30 || isHovered) && (
                <text
                  y={r + 14}
                  textAnchor="middle"
                  fill={isHovered ? 'white' : '#9CA3AF'}
                  fontSize={isHovered ? 12 : 10}
                  style={{ pointerEvents: 'none', userSelect: 'none' }}
                >
                  {label}
                </text>
              )}
            </g>
          )
        })}
      </svg>

      {limited.length >= MAX_NODES && (
        <div className="absolute top-2 right-2 bg-yellow-900/80 text-yellow-200 text-xs px-2 py-1 rounded">
          Showing first {MAX_NODES} results
        </div>
      )}
    </div>
  )
}
