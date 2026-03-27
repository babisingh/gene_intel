/**
 * DomainAgeChart — horizontal bar chart showing when each domain in the gene family
 * first appeared. Bars extend from domain origin (Mya) to the present.
 * Coloured by age tier.
 */

import { useState } from 'react'
import type { DomainAge } from '../../types/evolution'

const MAX_TIME = 3500

// Age tier → color
const TIER_COLORS: Record<string, string> = {
  'Ancient (>3.5 Gya)':    '#dc2626',  // red
  'Eukaryotic (~1.5 Gya)': '#ea580c',  // orange
  'Metazoan (~700 Mya)':   '#ca8a04',  // amber
  'Vertebrate (~500 Mya)': '#16a34a',  // green
  'Tetrapod (~360 Mya)':   '#0d9488',  // teal
  'Amniote (~300 Mya)':    '#0284c7',  // sky
  'Mammalian (~170 Mya)':  '#7c3aed',  // violet
  'Primate (~6 Mya)':      '#c026d3',  // fuchsia
  'Unknown origin':        '#475569',  // slate
  'Unknown':               '#475569',
}

function barColor(label: string): string {
  return TIER_COLORS[label] ?? '#475569'
}

// Log-scaled x position (0 = left, 1 = right = present)
function xFrac(time_mya: number): number {
  if (time_mya <= 0) return 1
  return 1 - Math.log10(time_mya + 1) / Math.log10(MAX_TIME + 1)
}

interface Props {
  domainAges: DomainAge[]
  onDomainSelect: (domain: string | null) => void
  selectedDomain: string | null
}

export function DomainAgeChart({ domainAges, onDomainSelect, selectedDomain }: Props) {
  const [hovered, setHovered] = useState<string | null>(null)

  if (!domainAges.length) {
    return (
      <div className="flex items-center justify-center h-32 text-gray-500 text-sm">
        No domain annotations available for this gene family.
      </div>
    )
  }

  const BAR_H = 22
  const LABEL_W = 160
  const CHART_W = 480
  const ROW_GAP = 6
  const TOTAL_H = domainAges.length * (BAR_H + ROW_GAP) + 40

  // Time axis ticks
  const ticks = [3500, 1500, 700, 430, 300, 87, 6, 0]
  const tickLabels: Record<number, string> = {
    3500: '3.5Ga', 1500: '1.5Ga', 700: '700M', 430: '430M',
    300: '300M', 87: '87M', 6: '6M', 0: 'Now',
  }

  return (
    <div className="overflow-auto">
      <svg
        viewBox={`0 0 ${LABEL_W + CHART_W + 20} ${TOTAL_H}`}
        width="100%"
        className="font-mono"
      >
        <rect width={LABEL_W + CHART_W + 20} height={TOTAL_H} fill="#0f172a" rx={6} />

        {/* Time axis ticks */}
        {ticks.map((t) => {
          const x = LABEL_W + xFrac(t) * CHART_W
          return (
            <g key={t}>
              <line x1={x} y1={16} x2={x} y2={TOTAL_H - 4} stroke="#1e293b" strokeWidth={1} />
              <text x={x} y={12} textAnchor="middle" fontSize={8} fill="#64748b">
                {tickLabels[t]}
              </text>
            </g>
          )
        })}

        {/* Domain bars */}
        {domainAges.map((da, i) => {
          const y = 20 + i * (BAR_H + ROW_GAP)
          const color = barColor(da.age.label)
          const barLeft = LABEL_W + xFrac(da.age.time_mya) * CHART_W
          const barWidth = CHART_W - xFrac(da.age.time_mya) * CHART_W
          const isSelected = selectedDomain === da.domain_id
          const isHov = hovered === da.domain_id

          return (
            <g
              key={da.domain_id}
              onClick={() => onDomainSelect(isSelected ? null : da.domain_id)}
              onMouseEnter={() => setHovered(da.domain_id)}
              onMouseLeave={() => setHovered(null)}
              style={{ cursor: 'pointer' }}
            >
              {/* Domain label */}
              <text
                x={LABEL_W - 6} y={y + BAR_H / 2 + 4}
                textAnchor="end" fontSize={9} fill={isSelected ? '#e2e8f0' : '#94a3b8'}
                fontFamily="sans-serif" fontWeight={isSelected ? 'bold' : 'normal'}
              >
                {da.domain_id.length > 20 ? da.domain_id.slice(0, 19) + '…' : da.domain_id}
              </text>

              {/* Background track */}
              <rect x={LABEL_W} y={y} width={CHART_W} height={BAR_H} fill="#1e293b" rx={3} />

              {/* Domain age bar */}
              <rect
                x={barLeft} y={y}
                width={Math.max(barWidth, 2)} height={BAR_H}
                fill={color}
                opacity={isSelected ? 1 : isHov ? 0.85 : 0.7}
                rx={3}
              />

              {/* Origin marker */}
              <line
                x1={barLeft} y1={y}
                x2={barLeft} y2={y + BAR_H}
                stroke="white" strokeWidth={2} opacity={0.6}
              />

              {/* Age label inside bar */}
              {barWidth > 60 && (
                <text
                  x={barLeft + 4} y={y + BAR_H / 2 + 4}
                  fontSize={8} fill="white" opacity={0.9}
                  fontFamily="sans-serif"
                >
                  {da.age.label}
                </text>
              )}

              {/* Selected/hover highlight */}
              {(isSelected || isHov) && (
                <rect
                  x={LABEL_W} y={y} width={CHART_W} height={BAR_H}
                  fill="none" stroke={isSelected ? '#60a5fa' : '#94a3b8'}
                  strokeWidth={1.5} rx={3}
                />
              )}

              {/* Tooltip on hover */}
              {isHov && (
                <text
                  x={LABEL_W + CHART_W / 2} y={y - 3}
                  textAnchor="middle" fontSize={8} fill="#94a3b8"
                  fontFamily="sans-serif"
                >
                  {da.age.label} · {da.species_present.join(', ').slice(0, 60)}
                </text>
              )}
            </g>
          )
        })}

        {/* Bottom axis label */}
        <text
          x={LABEL_W + CHART_W / 2}
          y={TOTAL_H - 2}
          textAnchor="middle" fontSize={9} fill="#475569"
          fontFamily="sans-serif"
        >
          ← More ancient · Evolutionary time · Present →
        </text>
      </svg>

      <p className="text-xs text-gray-500 mt-1 px-2">
        Click a bar to filter the phylogenetic tree to that domain's gain/loss events.
      </p>
    </div>
  )
}
