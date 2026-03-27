/**
 * DomainPresenceMatrix — replaces the bar chart with a readable grid.
 *
 * Layout:
 *   - Rows: domains, grouped by age tier, labelled with human-readable
 *     description (source badge + clean accession + description text)
 *   - Columns: 17 species in phylogenetic order (human → E. coli)
 *   - Cell: filled square (coloured by source) = domain present,
 *           empty dark square = domain absent
 *
 * Clicking a row selects that domain for tree filtering.
 * Domain IDs are shown as tooltips/secondary text, never as the primary label.
 */

import { useState } from 'react'
import type { DomainAge, SpeciesMeta } from '../../types/evolution'

// Phylogenetic order: human (most derived) → E. coli (most ancestral)
const PHYLO_ORDER = [
  '9606', '9598', '10090', '9913', '9031', '8665',
  '8364', '7955', '7227', '6239', '3702', '4530',
  '3218', '3055', '162425', '4932', '511145',
]

const SPECIES_ABBR: Record<string, string> = {
  '9606': 'Hum', '9598': 'Chi', '10090': 'Mou', '9913': 'Cow',
  '9031': 'Chk', '8665': 'Cob', '8364': 'Frg', '7955': 'Zfh',
  '7227': 'Fly', '6239': 'Wrm', '3702': 'Ara', '4530': 'Ric',
  '3218': 'Mos', '3055': 'Alg', '162425': 'Asp', '4932': 'Yst',
  '511145': 'Eco',
}

// Source → fill colour classes for present cells
const SOURCE_CELL: Record<string, string> = {
  Pfam: 'bg-blue-600',
  GO: 'bg-amber-500',
  InterPro: 'bg-teal-500',
  KEGG: 'bg-orange-500',
  PANTHER: 'bg-pink-500',
  Unknown: 'bg-purple-600',
}
const SOURCE_BADGE: Record<string, string> = {
  Pfam: 'bg-blue-900/60 text-blue-300 border-blue-800',
  GO: 'bg-amber-900/60 text-amber-300 border-amber-800',
  InterPro: 'bg-teal-900/60 text-teal-300 border-teal-800',
  KEGG: 'bg-orange-900/60 text-orange-300 border-orange-800',
  PANTHER: 'bg-pink-900/60 text-pink-300 border-pink-800',
  Unknown: 'bg-gray-800 text-gray-400 border-gray-700',
}

// Age tier → section header style
const TIER_HEADER: Record<string, string> = {
  'Ancient (>3.5 Gya)':    'bg-red-950/60 text-red-400 border-red-900',
  'Eukaryotic (~1.5 Gya)': 'bg-orange-950/60 text-orange-400 border-orange-900',
  'Metazoan (~700 Mya)':   'bg-amber-950/60 text-amber-400 border-amber-900',
  'Vertebrate (~500 Mya)': 'bg-green-950/60 text-green-400 border-green-900',
  'Tetrapod (~360 Mya)':   'bg-teal-950/60 text-teal-400 border-teal-900',
  'Amniote (~300 Mya)':    'bg-sky-950/60 text-sky-400 border-sky-900',
  'Mammalian (~170 Mya)':  'bg-violet-950/60 text-violet-400 border-violet-900',
  'Primate (~6 Mya)':      'bg-fuchsia-950/60 text-fuchsia-400 border-fuchsia-900',
  'Unknown origin':        'bg-gray-900 text-gray-500 border-gray-800',
}

interface Props {
  domainAges: DomainAge[]
  speciesMeta: Record<string, SpeciesMeta>
  onDomainSelect: (domain: string | null) => void
  selectedDomain: string | null
}

export function DomainPresenceMatrix({ domainAges, speciesMeta, onDomainSelect, selectedDomain }: Props) {
  const [hovered, setHovered] = useState<string | null>(null)

  if (!domainAges.length) {
    return (
      <div className="flex items-center justify-center h-32 text-gray-500 text-sm">
        No domain annotations available for this gene family.
      </div>
    )
  }

  // Group domains by age tier label
  const grouped: Record<string, DomainAge[]> = {}
  for (const da of domainAges) {
    const tier = da.age.label
    if (!grouped[tier]) grouped[tier] = []
    grouped[tier].push(da)
  }

  // Ordered tier labels (most ancient first)
  const tierOrder = [
    'Ancient (>3.5 Gya)', 'Eukaryotic (~1.5 Gya)', 'Metazoan (~700 Mya)',
    'Vertebrate (~500 Mya)', 'Tetrapod (~360 Mya)', 'Amniote (~300 Mya)',
    'Mammalian (~170 Mya)', 'Primate (~6 Mya)', 'Unknown origin',
  ]
  const tiers = tierOrder.filter((t) => grouped[t])

  return (
    <div className="overflow-auto">
      <table className="w-full text-xs border-collapse min-w-max">
        <thead>
          <tr>
            {/* Domain label column header */}
            <th className="sticky left-0 bg-gray-900 z-10 text-left pb-2 pr-3 min-w-[260px]">
              <span className="text-gray-500 font-normal">Domain (description · accession)</span>
            </th>
            {/* Species column headers */}
            {PHYLO_ORDER.map((taxon) => (
              <th key={taxon} className="pb-2 px-0.5 font-normal" title={speciesMeta[taxon]?.common ?? taxon}>
                <div className="flex flex-col items-center gap-0.5">
                  <span className="text-gray-500" style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)', fontSize: 9 }}>
                    {SPECIES_ABBR[taxon] ?? taxon.slice(0, 3)}
                  </span>
                </div>
              </th>
            ))}
          </tr>
        </thead>

        <tbody>
          {tiers.map((tier) => (
            <>
              {/* Age tier section header */}
              <tr key={`tier-${tier}`}>
                <td
                  colSpan={18}
                  className={`py-1 px-2 text-xs font-semibold border-y ${TIER_HEADER[tier] ?? 'bg-gray-900 text-gray-400 border-gray-800'}`}
                >
                  {tier}
                  <span className="ml-2 font-normal opacity-60">
                    {grouped[tier].length} domain{grouped[tier].length !== 1 ? 's' : ''}
                  </span>
                </td>
              </tr>

              {/* Domain rows */}
              {grouped[tier].map((da) => {
                const isSelected = selectedDomain === da.domain_id
                const isHov = hovered === da.domain_id
                const presentSet = new Set(da.taxon_ids_present)
                const source = da.source || 'Unknown'
                const cellColor = SOURCE_CELL[source] ?? SOURCE_CELL.Unknown
                const badgeStyle = SOURCE_BADGE[source] ?? SOURCE_BADGE.Unknown

                // Build display label: description if available, else display_id
                const primaryLabel = da.description
                  ? da.description.length > 40
                    ? da.description.slice(0, 38) + '…'
                    : da.description
                  : da.display_id

                const secondaryLabel = da.description ? da.display_id : ''

                return (
                  <tr
                    key={da.domain_id}
                    onClick={() => onDomainSelect(isSelected ? null : da.domain_id)}
                    onMouseEnter={() => setHovered(da.domain_id)}
                    onMouseLeave={() => setHovered(null)}
                    className={`cursor-pointer transition-colors ${
                      isSelected ? 'bg-blue-950/40' : isHov ? 'bg-gray-800/40' : ''
                    }`}
                    title={`${da.domain_id} — ${da.description || 'no description'}`}
                  >
                    {/* Domain label */}
                    <td className="sticky left-0 bg-gray-950 py-1 pr-3">
                      <div className="flex items-center gap-1.5">
                        {/* Source badge */}
                        <span className={`flex-shrink-0 text-[9px] px-1 py-0.5 rounded border font-mono ${badgeStyle}`}>
                          {source.slice(0, 4)}
                        </span>
                        {/* Description / accession */}
                        <span className={`${isSelected ? 'text-white' : 'text-gray-300'} font-medium`}>
                          {primaryLabel}
                        </span>
                        {secondaryLabel && (
                          <span className="text-gray-600 font-mono text-[9px]">{secondaryLabel}</span>
                        )}
                      </div>
                    </td>

                    {/* Species presence cells */}
                    {PHYLO_ORDER.map((taxon) => {
                      const present = presentSet.has(taxon)
                      return (
                        <td key={taxon} className="px-0.5 py-1">
                          <div
                            className={`w-4 h-4 rounded-sm mx-auto ${
                              present
                                ? `${cellColor} opacity-90`
                                : 'bg-gray-800/60 border border-gray-800'
                            } ${isSelected && present ? 'ring-1 ring-blue-400' : ''}`}
                            title={present
                              ? `${speciesMeta[taxon]?.common}: present`
                              : `${speciesMeta[taxon]?.common}: absent`}
                          />
                        </td>
                      )
                    })}
                  </tr>
                )
              })}
            </>
          ))}
        </tbody>
      </table>

      {/* Legend + instructions */}
      <div className="mt-3 px-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-gray-500 border-t border-gray-800 pt-2">
        <span className="text-gray-600">Sources:</span>
        {Object.entries(SOURCE_BADGE).filter(([s]) => s !== 'Unknown').map(([source, cls]) => (
          <span key={source} className={`px-1.5 py-0.5 rounded border font-mono ${cls}`}>{source}</span>
        ))}
        <span className="ml-auto">Click a row to filter the phylo tree to that domain's gain/loss events.</span>
      </div>
    </div>
  )
}
