/**
 * PhyloTreeView — SVG phylogenetic tree with domain gain/loss overlays.
 *
 * Layout (log-scaled time axis):
 *   - X axis: time in Mya, right = present (0), left = ancient (3500)
 *   - Y axis: species ordered phylogenetically top → bottom
 *   - Leaf nodes: coloured circle (green = present, gray = absent)
 *   - Branch lines: horizontal + vertical SVG lines
 *   - Events: ▲ gain (green), ▼ loss (red) icons on relevant branches
 *   - Hovering a leaf shows species name tooltip
 */

import { useMemo, useState } from 'react'
import type { PhyloNode, DomainEvent, SpeciesMeta } from '../../types/evolution'

// Canvas dimensions
const W = 820
const H = 580
const LEFT = 60    // x-axis label area
const RIGHT = 220  // species label + dots area
const TREE_W = W - LEFT - RIGHT  // 540px
const TOP = 24
const ROW_H = (H - TOP - 16) / 17  // ~31px per species

const MAX_TIME = 3500

// Log-scaled x position: older = further left
function xPos(time_mya: number): number {
  if (time_mya <= 0) return LEFT + TREE_W
  return LEFT + TREE_W - (TREE_W * Math.log10(time_mya + 1)) / Math.log10(MAX_TIME + 1)
}

const PHYLO_ORDER = [
  '9606', '9598', '10090', '9913', '9031', '8665',
  '8364', '7955', '7227', '6239', '3702', '4530',
  '3218', '3055', '162425', '4932', '511145',
]

function leafY(taxon_id: string): number {
  const idx = PHYLO_ORDER.indexOf(taxon_id)
  return TOP + (idx + 0.5) * ROW_H
}

interface LayoutNode {
  name: string
  label: string
  time_mya: number
  taxon_id?: string
  x: number
  y: number
  children?: LayoutNode[]
}

function buildLayout(node: PhyloNode): LayoutNode {
  const x = xPos(node.time_mya)
  if (node.taxon_id) {
    return { name: node.name, label: node.label, time_mya: node.time_mya, taxon_id: node.taxon_id, x, y: leafY(node.taxon_id) }
  }
  const kids = (node.children ?? []).map(buildLayout)
  const ys = kids.map((k) => k.y)
  const y = ys.length ? (Math.min(...ys) + Math.max(...ys)) / 2 : H / 2
  return { name: node.name, label: node.label, time_mya: node.time_mya, x, y, children: kids }
}

function collectLines(
  node: LayoutNode,
  parentX: number | null,
  acc: { x1: number; y1: number; x2: number; y2: number }[],
) {
  if (parentX !== null) {
    // Horizontal line: parent.x → node.x at node.y
    acc.push({ x1: parentX, y1: node.y, x2: node.x, y2: node.y })
  }
  if (node.children && node.children.length) {
    const ys = node.children.map((c) => c.y)
    // Vertical line at node.x connecting all children
    acc.push({ x1: node.x, y1: Math.min(...ys), x2: node.x, y2: Math.max(...ys) })
    for (const child of node.children) collectLines(child, node.x, acc)
  }
}

// Collect all leaf layout nodes
function collectLeaves(node: LayoutNode): LayoutNode[] {
  if (node.taxon_id) return [node]
  return (node.children ?? []).flatMap(collectLeaves)
}

// Time axis ticks (log-scaled)
const TIME_TICKS = [3500, 1500, 900, 700, 500, 360, 300, 170, 87, 6, 0]
const TIME_LABELS: Record<number, string> = {
  3500: '3.5 Gya', 1500: '1.5 Gya', 900: '900 Mya', 700: '700 Mya',
  500: '500 Mya', 360: '360 Mya', 300: '300 Mya', 170: '170 Mya',
  87: '87 Mya', 6: '6 Mya', 0: 'Now',
}

interface Props {
  tree: PhyloNode
  speciesMeta: Record<string, SpeciesMeta>
  presentTaxons: Set<string>          // for gene family presence
  domainEvents: DomainEvent[]
  selectedDomain: string | null       // highlight events for one domain
}

export function PhyloTreeView({ tree, speciesMeta, presentTaxons, domainEvents, selectedDomain }: Props) {
  const [hovered, setHovered] = useState<string | null>(null)

  const layout = useMemo(() => buildLayout(tree), [tree])
  const lines = useMemo(() => {
    const acc: { x1: number; y1: number; x2: number; y2: number }[] = []
    collectLines(layout, null, acc)
    return acc
  }, [layout])
  const leaves = useMemo(() => collectLeaves(layout), [layout])

  // Filter events to selected domain (or all if none selected)
  const visibleEvents = selectedDomain
    ? domainEvents.filter((e) => e.domain_id === selectedDomain)
    : domainEvents

  // Map node name → y position for placing event icons
  const nodeYMap = useMemo(() => {
    const map: Record<string, number> = {}
    function traverse(n: LayoutNode) {
      map[n.name] = n.y
      for (const c of n.children ?? []) traverse(c)
    }
    traverse(layout)
    return map
  }, [layout])

  const nodeXMap = useMemo(() => {
    const map: Record<string, number> = {}
    function traverse(n: LayoutNode) {
      map[n.name] = n.x
      for (const c of n.children ?? []) traverse(c)
    }
    traverse(layout)
    return map
  }, [layout])

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      width="100%"
      height="100%"
      style={{ maxHeight: '100%' }}
      className="font-mono"
    >
      {/* Background */}
      <rect width={W} height={H} fill="#0f172a" rx={6} />

      {/* Time axis grid lines + labels */}
      {TIME_TICKS.map((t) => {
        const x = xPos(t)
        return (
          <g key={t}>
            <line x1={x} y1={TOP - 8} x2={x} y2={H - 12} stroke="#1e293b" strokeWidth={1} />
            <text x={x} y={TOP - 12} textAnchor="middle" fontSize={8} fill="#475569">
              {TIME_LABELS[t]}
            </text>
          </g>
        )
      })}

      {/* Branch lines */}
      {lines.map((l, i) => (
        <line
          key={i}
          x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2}
          stroke="#334155" strokeWidth={1.5}
        />
      ))}

      {/* Domain gain/loss event markers */}
      {visibleEvents.map((ev, i) => {
        const y = nodeYMap[ev.node]
        const x = nodeXMap[ev.node]
        if (y == null || x == null) return null
        const isGain = ev.type === 'gain'
        return (
          <g key={i} transform={`translate(${x - 6}, ${y - 6})`}>
            <circle r={6} cx={6} cy={6} fill={isGain ? '#16a34a' : '#dc2626'} opacity={0.9} />
            <text x={6} y={10} textAnchor="middle" fontSize={9} fill="white" fontWeight="bold">
              {isGain ? '+' : '−'}
            </text>
            <title>{ev.domain_id}: {isGain ? 'gained' : 'lost'} at {ev.node_label} (~{ev.time_mya} Mya)</title>
          </g>
        )
      })}

      {/* Leaf nodes */}
      {leaves.map((leaf) => {
        const taxon = leaf.taxon_id!
        const present = presentTaxons.has(taxon)
        const meta = speciesMeta[taxon]
        const label = meta?.short ?? taxon
        const isHovered = hovered === taxon
        const LABEL_X = LEFT + TREE_W + 12

        return (
          <g
            key={taxon}
            onMouseEnter={() => setHovered(taxon)}
            onMouseLeave={() => setHovered(null)}
            style={{ cursor: 'default' }}
          >
            {/* Connector line from tree to label area */}
            <line
              x1={leaf.x} y1={leaf.y}
              x2={LABEL_X - 4} y2={leaf.y}
              stroke={present ? '#22c55e' : '#374151'}
              strokeWidth={isHovered ? 2 : 1}
              strokeDasharray={present ? 'none' : '3,3'}
            />
            {/* Leaf circle */}
            <circle
              cx={leaf.x} cy={leaf.y} r={isHovered ? 6 : 5}
              fill={present ? '#22c55e' : '#374151'}
              stroke={isHovered ? '#white' : 'none'}
              strokeWidth={1.5}
            />
            {/* Species label */}
            <text
              x={LABEL_X} y={leaf.y + 4}
              fontSize={isHovered ? 11 : 10}
              fill={present ? '#e2e8f0' : '#6b7280'}
              fontWeight={present ? '500' : 'normal'}
              fontFamily="sans-serif"
            >
              {label}
            </text>
            {/* Hover tooltip */}
            {isHovered && (
              <text
                x={LABEL_X} y={leaf.y - 8}
                fontSize={9} fill="#94a3b8" fontFamily="sans-serif"
              >
                {meta?.common ?? taxon} · taxon {taxon}
              </text>
            )}
          </g>
        )
      })}

      {/* Legend */}
      <g transform={`translate(${LEFT}, ${H - 12})`}>
        <circle cx={4} cy={0} r={4} fill="#22c55e" />
        <text x={12} y={4} fontSize={9} fill="#94a3b8" fontFamily="sans-serif">Present</text>
        <circle cx={56} cy={0} r={4} fill="#374151" />
        <text x={64} y={4} fontSize={9} fill="#94a3b8" fontFamily="sans-serif">Absent</text>
        <circle cx={104} cy={0} r={5} fill="#16a34a" />
        <text x={113} y={4} fontSize={9} fill="#94a3b8" fontFamily="sans-serif">+ Gained</text>
        <circle cx={162} cy={0} r={5} fill="#dc2626" />
        <text x={171} y={4} fontSize={9} fill="#94a3b8" fontFamily="sans-serif">− Lost</text>
      </g>
    </svg>
  )
}
