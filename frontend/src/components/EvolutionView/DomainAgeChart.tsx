/**
 * DomainPresenceMatrix — domain × species heatmap with:
 *  - Two-part domain label: full accession ID  |  human-readable description
 *  - Age-tier section grouping (Ancient → Primate)
 *  - Species column headers: emoji + full common name (rotated)
 *  - Click species header → filter rows to domains present in that species
 *  - Zoom in / out controls
 *  - Auto-generated 3–4 sentence summary at the bottom
 */

import { useState, useMemo } from 'react'
import type { DomainAge, SpeciesMeta } from '../../types/evolution'

// ── Phylogenetic column order (human → E. coli) ──────────────────────────────
const PHYLO_ORDER = [
  '9606','9598','10090','9913','9031','8665',
  '8364','7955','7227','6239','3702','4530',
  '3218','3055','162425','4932','511145',
]

// ── Species emojis ────────────────────────────────────────────────────────────
const SPECIES_EMOJI: Record<string, string> = {
  '9606':   '🧑',  // Human
  '9598':   '🐒',  // Chimp
  '10090':  '🐭',  // Mouse
  '9913':   '🐮',  // Cow
  '9031':   '🐔',  // Chicken
  '8665':   '🐟',  // Coelacanth
  '8364':   '🐸',  // Frog
  '7955':   '🐠',  // Zebrafish
  '7227':   '🪰',  // Fly
  '6239':   '🪱',  // Worm (C. elegans)
  '3702':   '🌱',  // Arabidopsis
  '4530':   '🌾',  // Rice
  '3218':   '🌿',  // Moss
  '3055':   '🟢',  // Chlamydomonas (alga)
  '162425': '🍄',  // Aspergillus (fungus)
  '4932':   '🧫',  // Yeast
  '511145': '🦠',  // E. coli
}

// ── Fallback full names (if speciesMeta not available) ───────────────────────
const SPECIES_FULL: Record<string, string> = {
  '9606':   'Human',          '9598':   'Chimpanzee',
  '10090':  'Mouse',          '9913':   'Cow',
  '9031':   'Chicken',        '8665':   'Coelacanth',
  '8364':   'Frog',           '7955':   'Zebrafish',
  '7227':   'Fruit Fly',      '6239':   'C. elegans',
  '3702':   'Arabidopsis',    '4530':   'Rice',
  '3218':   'Moss',           '3055':   'Chlamydomonas',
  '162425': 'Aspergillus',    '4932':   'Yeast',
  '511145': 'E. coli',
}

// ── Source colour maps ────────────────────────────────────────────────────────
const SOURCE_CELL: Record<string, string> = {
  Pfam: 'bg-blue-600',       GO: 'bg-amber-500',
  InterPro: 'bg-teal-500',   KEGG: 'bg-orange-500',
  PANTHER: 'bg-pink-500',    Unknown: 'bg-purple-600',
}
const SOURCE_BADGE: Record<string, string> = {
  Pfam: 'bg-blue-900/60 text-blue-300 border-blue-800',
  GO: 'bg-amber-900/60 text-amber-300 border-amber-800',
  InterPro: 'bg-teal-900/60 text-teal-300 border-teal-800',
  KEGG: 'bg-orange-900/60 text-orange-300 border-orange-800',
  PANTHER: 'bg-pink-900/60 text-pink-300 border-pink-800',
  Unknown: 'bg-gray-800 text-gray-400 border-gray-700',
}

// ── Age-tier header colours ───────────────────────────────────────────────────
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
const TIER_ORDER = [
  'Ancient (>3.5 Gya)', 'Eukaryotic (~1.5 Gya)', 'Metazoan (~700 Mya)',
  'Vertebrate (~500 Mya)', 'Tetrapod (~360 Mya)', 'Amniote (~300 Mya)',
  'Mammalian (~170 Mya)', 'Primate (~6 Mya)', 'Unknown origin',
]

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Ensure GO IDs always show "GO:NNNNNNN". Backend now provides this but guard anyway. */
function formatDisplayId(displayId: string, source: string): string {
  if (!displayId) return '—'
  if (source === 'GO' && /^\d+$/.test(displayId)) return `GO:${displayId.padStart(7, '0')}`
  return displayId
}

// ── Summary generator ─────────────────────────────────────────────────────────
function buildSummary(
  domainAges: DomainAge[],
  filteredSpecies: string | null,
  speciesMeta: Record<string, SpeciesMeta>,
): string {
  if (!domainAges.length) return 'No domain annotations were found for this gene family.'

  const total = domainAges.length
  const tierCounts: Record<string, number> = {}
  for (const da of domainAges) tierCounts[da.age.label] = (tierCounts[da.age.label] ?? 0) + 1

  const dominantTier = Object.entries(tierCounts).sort(([, a], [, b]) => b - a)[0]
  const pct = Math.round((dominantTier[1] / total) * 100)

  const perSpecies = PHYLO_ORDER.map((t) => ({
    taxon: t,
    count: domainAges.filter((da) => da.taxon_ids_present.includes(t)).length,
    name: speciesMeta[t]?.common ?? SPECIES_FULL[t] ?? t,
  }))
  const richest = perSpecies.reduce((a, b) => (a.count > b.count ? a : b))
  const conserved = domainAges.filter((da) => da.taxon_ids_present.length === PHYLO_ORDER.length).length
  const humanOnly = domainAges.filter((da) =>
    da.taxon_ids_present.includes('9606') && da.taxon_ids_present.length === 1,
  ).length

  const filterNote = filteredSpecies
    ? ` Filtered to ${speciesMeta[filteredSpecies]?.common ?? SPECIES_FULL[filteredSpecies] ?? filteredSpecies}: ${
        domainAges.filter((da) => da.taxon_ids_present.includes(filteredSpecies)).length
      } domains present.`
    : ''

  const parts = [
    `This matrix shows ${total} annotated domains across up to 17 species.`,
    `The majority (${pct}%) originated at the ${dominantTier[0].replace(/\s*\(.*?\)/, '')} level, indicating when the core domain architecture was established.`,
    richest.count > 0
      ? `${richest.name} carries the highest domain count (${richest.count}), while ${conserved} domain${conserved !== 1 ? 's are' : ' is'} universally conserved across all 17 species.`
      : '',
    humanOnly > 0
      ? `${humanOnly} domain${humanOnly !== 1 ? 's appear' : ' appears'} exclusively in human, representing lineage-specific innovations.`
      : 'No human-exclusive domains were detected — this gene maintains a broadly conserved domain structure.',
  ]

  return parts.filter(Boolean).join(' ') + filterNote
}

// ── Component ─────────────────────────────────────────────────────────────────
interface Props {
  domainAges: DomainAge[]
  speciesMeta: Record<string, SpeciesMeta>
  onDomainSelect: (domain: string | null) => void
  selectedDomain: string | null
}

export function DomainPresenceMatrix({ domainAges, speciesMeta, onDomainSelect, selectedDomain }: Props) {
  const [hovered, setHovered] = useState<string | null>(null)
  const [zoom, setZoom] = useState(0.85)
  const [filteredSpecies, setFilteredSpecies] = useState<string | null>(null)
  const [hoveredSpecies, setHoveredSpecies] = useState<string | null>(null)

  const displayRows = useMemo(() =>
    filteredSpecies
      ? domainAges.filter((da) => da.taxon_ids_present.includes(filteredSpecies))
      : domainAges,
    [domainAges, filteredSpecies],
  )

  // Group filtered rows by tier
  const grouped = useMemo(() => {
    const g: Record<string, DomainAge[]> = {}
    for (const da of displayRows) {
      const tier = da.age.label
      if (!g[tier]) g[tier] = []
      g[tier].push(da)
    }
    return g
  }, [displayRows])

  const tiers = TIER_ORDER.filter((t) => grouped[t])

  const summary = useMemo(
    () => buildSummary(domainAges, filteredSpecies, speciesMeta),
    [domainAges, filteredSpecies, speciesMeta],
  )

  if (!domainAges.length) {
    return (
      <div className="flex items-center justify-center h-32 text-gray-500 text-sm">
        No domain annotations available for this gene family.
      </div>
    )
  }

  const handleSpeciesClick = (taxon: string) => {
    setFilteredSpecies((prev) => (prev === taxon ? null : taxon))
  }

  return (
    <div className="flex flex-col h-full gap-2">

      {/* ── Controls bar ──────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 px-1 flex-shrink-0">
        {/* Zoom controls */}
        <div className="flex items-center gap-1 text-xs text-gray-500">
          <span>Zoom</span>
          <button
            onClick={() => setZoom((z) => Math.max(0.4, parseFloat((z - 0.1).toFixed(1))))}
            className="w-6 h-6 flex items-center justify-center rounded bg-gray-800 hover:bg-gray-700 text-gray-300 font-bold"
            title="Zoom out"
          >−</button>
          <span className="w-10 text-center font-mono text-gray-400">{Math.round(zoom * 100)}%</span>
          <button
            onClick={() => setZoom((z) => Math.min(1.5, parseFloat((z + 0.1).toFixed(1))))}
            className="w-6 h-6 flex items-center justify-center rounded bg-gray-800 hover:bg-gray-700 text-gray-300 font-bold"
            title="Zoom in"
          >+</button>
          <button
            onClick={() => setZoom(0.85)}
            className="px-2 h-6 flex items-center rounded bg-gray-800 hover:bg-gray-700 text-gray-500 text-[10px]"
            title="Reset zoom"
          >reset</button>
        </div>

        {/* Active species filter badge */}
        {filteredSpecies && (
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-blue-900/40 border border-blue-700 text-xs text-blue-300">
            <span>
              {SPECIES_EMOJI[filteredSpecies]}{' '}
              {speciesMeta[filteredSpecies]?.common ?? SPECIES_FULL[filteredSpecies]}
            </span>
            <span className="text-blue-500 text-[10px]">({displayRows.length} domains)</span>
            <button
              onClick={() => setFilteredSpecies(null)}
              className="ml-0.5 text-blue-500 hover:text-blue-300 font-bold leading-none"
              title="Clear species filter"
            >×</button>
          </div>
        )}

        <span className="ml-auto text-[10px] text-gray-600 italic">
          {filteredSpecies
            ? `Click species again to clear filter · Click a row to highlight on phylo tree`
            : `Click a species column to filter · Click a row to highlight on phylo tree`}
        </span>
      </div>

      {/* ── Scrollable matrix wrapper ──────────────────────────────────────── */}
      <div className="flex-1 overflow-auto rounded border border-gray-800 bg-gray-950">
        <div
          style={{
            transform: `scale(${zoom})`,
            transformOrigin: 'top left',
            width: `${(1 / zoom) * 100}%`,
          }}
        >
          <table className="text-xs border-collapse">
            <thead>
              <tr>
                {/* Domain label column header */}
                <th className="sticky left-0 bg-gray-900 z-20 text-left pb-2 pr-2 min-w-[380px]">
                  <div className="flex gap-2 text-[10px] text-gray-500 font-normal border-b border-gray-800 pb-1">
                    <span className="w-[110px] flex-shrink-0">Accession ID</span>
                    <span>Description</span>
                  </div>
                </th>

                {/* Species column headers */}
                {PHYLO_ORDER.map((taxon) => {
                  const fullName = speciesMeta[taxon]?.common ?? SPECIES_FULL[taxon] ?? taxon
                  const emoji = SPECIES_EMOJI[taxon] ?? '🔬'
                  const isFiltered = filteredSpecies === taxon
                  const isHov = hoveredSpecies === taxon
                  const domainCount = domainAges.filter((da) => da.taxon_ids_present.includes(taxon)).length

                  return (
                    <th
                      key={taxon}
                      className={`pb-2 px-0.5 font-normal cursor-pointer transition-colors select-none ${
                        isFiltered ? 'bg-blue-950/40' : isHov ? 'bg-gray-800/30' : ''
                      }`}
                      onClick={() => handleSpeciesClick(taxon)}
                      onMouseEnter={() => setHoveredSpecies(taxon)}
                      onMouseLeave={() => setHoveredSpecies(null)}
                      title={`${fullName} — ${domainCount} domains\nClick to filter matrix`}
                    >
                      <div className="flex flex-col items-center gap-0.5 w-7">
                        <span style={{ fontSize: 13 }}>{emoji}</span>
                        <span
                          className={`font-normal whitespace-nowrap ${isFiltered ? 'text-blue-300' : 'text-gray-400'}`}
                          style={{
                            writingMode: 'vertical-rl',
                            transform: 'rotate(180deg)',
                            fontSize: 9,
                            lineHeight: 1.2,
                          }}
                        >
                          {fullName}
                        </span>
                        {isFiltered && (
                          <div className="w-1.5 h-1.5 rounded-full bg-blue-400 mt-0.5" />
                        )}
                      </div>
                    </th>
                  )
                })}
              </tr>
            </thead>

            <tbody>
              {tiers.length === 0 ? (
                <tr>
                  <td colSpan={18} className="py-8 text-center text-gray-600 text-xs italic">
                    No domains found in{' '}
                    {speciesMeta[filteredSpecies!]?.common ?? SPECIES_FULL[filteredSpecies!] ?? filteredSpecies}.
                  </td>
                </tr>
              ) : (
                tiers.map((tier) => (
                  <>
                    {/* Age-tier section header */}
                    <tr key={`tier-${tier}`}>
                      <td
                        colSpan={18}
                        className={`py-1 px-2 text-xs font-semibold border-y ${
                          TIER_HEADER[tier] ?? 'bg-gray-900 text-gray-400 border-gray-800'
                        }`}
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
                      const fullId = formatDisplayId(da.display_id, source)
                      const desc = da.description || ''

                      return (
                        <tr
                          key={da.domain_id}
                          onClick={() => onDomainSelect(isSelected ? null : da.domain_id)}
                          onMouseEnter={() => setHovered(da.domain_id)}
                          onMouseLeave={() => setHovered(null)}
                          className={`cursor-pointer transition-colors ${
                            isSelected
                              ? 'bg-blue-950/40'
                              : isHov
                              ? 'bg-gray-800/30'
                              : ''
                          }`}
                        >
                          {/* ── Domain label cell: [badge+ID] | [description] ── */}
                          <td className="sticky left-0 bg-gray-950 py-0.5 pr-3 min-w-[380px]">
                            <div className="flex items-center gap-1.5">
                              {/* Source badge */}
                              <span
                                className={`flex-shrink-0 text-[9px] px-1 py-0.5 rounded border font-mono ${badgeStyle}`}
                              >
                                {source.slice(0, 4)}
                              </span>

                              {/* Fixed-width accession */}
                              <span
                                className="flex-shrink-0 w-[90px] font-mono text-[10px] text-gray-400 truncate"
                                title={fullId}
                              >
                                {fullId}
                              </span>

                              {/* Separator */}
                              <span className="text-gray-700 flex-shrink-0">·</span>

                              {/* Description */}
                              {desc ? (
                                <span
                                  className={`${isSelected ? 'text-white' : 'text-gray-300'} truncate max-w-[180px]`}
                                  title={desc}
                                >
                                  {desc}
                                </span>
                              ) : (
                                <span className="text-gray-700 italic text-[10px]">no description</span>
                              )}
                            </div>
                          </td>

                          {/* ── Species presence cells ── */}
                          {PHYLO_ORDER.map((taxon) => {
                            const present = presentSet.has(taxon)
                            const isSpeciesHighlighted = filteredSpecies === taxon || hoveredSpecies === taxon
                            return (
                              <td
                                key={taxon}
                                className={`px-0.5 py-0.5 ${isSpeciesHighlighted ? 'bg-blue-950/20' : ''}`}
                              >
                                <div
                                  className={`w-4 h-4 rounded-sm mx-auto transition-all ${
                                    present
                                      ? `${cellColor} opacity-90 ${isSelected ? 'ring-1 ring-blue-400' : ''}`
                                      : 'bg-gray-800/60 border border-gray-800/80'
                                  }`}
                                  title={`${speciesMeta[taxon]?.common ?? SPECIES_FULL[taxon]}: ${present ? 'present' : 'absent'}\n${desc || fullId}`}
                                />
                              </td>
                            )
                          })}
                        </tr>
                      )
                    })}
                  </>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Source legend ─────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-1 text-[10px] text-gray-500 flex-shrink-0">
        <span className="text-gray-600">Sources:</span>
        {Object.entries(SOURCE_BADGE)
          .filter(([s]) => s !== 'Unknown')
          .map(([source, cls]) => (
            <span key={source} className={`px-1.5 py-0.5 rounded border font-mono ${cls}`}>
              {source}
            </span>
          ))}
      </div>

      {/* ── Auto-generated summary ─────────────────────────────────────────── */}
      <div className="flex-shrink-0 rounded-lg bg-gray-900/60 border border-gray-800 px-3 py-2 text-[11px] text-gray-400 leading-relaxed">
        <span className="text-gray-500 font-semibold text-[10px] uppercase tracking-wide mr-2">Summary</span>
        {summary}
      </div>
    </div>
  )
}
