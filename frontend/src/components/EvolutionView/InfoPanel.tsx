/**
 * InfoPanel — shows the raw data, calculations, and methodology behind
 * the evolutionary analysis. Scientific "receipts" for every number shown.
 */

import type { EvolutionResponse } from '../../types/evolution'

interface Props {
  data: EvolutionResponse
}

export function InfoPanel({ data }: Props) {
  const { species_profiles, domain_ages, domain_events, gene_name } = data

  const presentNames = species_profiles.map((p) => p.common_name)
  const allTaxons = Object.keys(data.species_meta)
  const absentNames = allTaxons
    .filter((t) => !species_profiles.find((p) => p.taxon_id === t))
    .map((t) => data.species_meta[t]?.common ?? t)

  // Exon count stats
  const exonCounts = species_profiles.map((p) => p.exon_count).filter((x): x is number => x != null)
  const utrRatios = species_profiles.map((p) => p.utr_cds_ratio).filter((x): x is number => x != null)
  const cdsSizes = species_profiles.map((p) => p.cds_length).filter((x): x is number => x != null)
  const isoformCounts = species_profiles.map((p) => p.transcript_count).filter((x) => x > 0)

  const gainEvents = domain_events.filter((e) => e.type === 'gain')
  const lossEvents = domain_events.filter((e) => e.type === 'loss')

  function stat(vals: number[]) {
    if (!vals.length) return 'N/A'
    const min = Math.min(...vals)
    const max = Math.max(...vals)
    const avg = vals.reduce((a, b) => a + b, 0) / vals.length
    return `${min}–${max} (avg ${avg.toFixed(1)})`
  }

  return (
    <div className="p-4 space-y-6 text-sm text-gray-300 overflow-y-auto">

      {/* Gene presence summary */}
      <section>
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
          Species Distribution
        </h3>
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-gray-800/50 rounded-lg p-3">
            <div className="text-2xl font-bold text-green-400">{species_profiles.length}</div>
            <div className="text-xs text-gray-500 mt-0.5">species with {gene_name}</div>
          </div>
          <div className="bg-gray-800/50 rounded-lg p-3">
            <div className="text-2xl font-bold text-gray-500">{absentNames.length}</div>
            <div className="text-xs text-gray-500 mt-0.5">species without {gene_name}</div>
          </div>
        </div>
        <div className="mt-3 space-y-1.5">
          <div>
            <span className="text-xs text-green-400 font-medium">Present in: </span>
            <span className="text-xs text-gray-300">{presentNames.join(', ')}</span>
          </div>
          {absentNames.length > 0 && (
            <div>
              <span className="text-xs text-gray-500 font-medium">Absent in: </span>
              <span className="text-xs text-gray-500">{absentNames.join(', ')}</span>
            </div>
          )}
        </div>
      </section>

      {/* Structural metrics table */}
      <section>
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
          Structural Metrics Across Species
        </h3>
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="border-b border-gray-700">
              <th className="text-left text-gray-500 pb-1.5 pr-3">Metric</th>
              <th className="text-right text-gray-500 pb-1.5">Range (min–max, avg)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            <tr>
              <td className="py-1.5 pr-3 text-gray-400">Exon count</td>
              <td className="text-right font-mono text-gray-300">{stat(exonCounts)}</td>
            </tr>
            <tr>
              <td className="py-1.5 pr-3 text-gray-400">CDS length (bp)</td>
              <td className="text-right font-mono text-gray-300">{stat(cdsSizes)}</td>
            </tr>
            <tr>
              <td className="py-1.5 pr-3 text-gray-400">UTR/CDS ratio</td>
              <td className="text-right font-mono text-gray-300">{stat(utrRatios.map((r) => parseFloat(r.toFixed(3))))}</td>
            </tr>
            <tr>
              <td className="py-1.5 pr-3 text-gray-400">Transcript isoforms</td>
              <td className="text-right font-mono text-gray-300">{stat(isoformCounts)}</td>
            </tr>
            <tr>
              <td className="py-1.5 pr-3 text-gray-400">Unique domains</td>
              <td className="text-right font-mono text-gray-300">{domain_ages.length}</td>
            </tr>
          </tbody>
        </table>
      </section>

      {/* Per-species details */}
      <section>
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
          Per-Species Profile
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="border-b border-gray-700">
                {['Species', 'Exons', 'CDS (bp)', 'UTR/CDS', 'Isoforms', 'Domains'].map((h) => (
                  <th key={h} className="text-left text-gray-500 pb-1.5 pr-3 whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {species_profiles.map((p) => (
                <tr key={p.taxon_id} className="hover:bg-gray-800/30">
                  <td className="py-1 pr-3 text-gray-300 whitespace-nowrap">{p.common_name}</td>
                  <td className="py-1 pr-3 font-mono text-gray-400">{p.exon_count ?? '—'}</td>
                  <td className="py-1 pr-3 font-mono text-gray-400">{p.cds_length?.toLocaleString() ?? '—'}</td>
                  <td className="py-1 pr-3 font-mono text-gray-400">
                    {p.utr_cds_ratio != null ? p.utr_cds_ratio.toFixed(3) : '—'}
                  </td>
                  <td className="py-1 pr-3 font-mono text-gray-400">{p.transcript_count}</td>
                  <td className="py-1 text-gray-400">{(p.domains ?? []).length}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Domain events */}
      <section>
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
          Dollo Parsimony Domain Events
          <span className="ml-2 text-gray-600 normal-case font-normal">
            ({gainEvents.length} gains, {lossEvents.length} losses)
          </span>
        </h3>
        <p className="text-xs text-gray-600 mb-3">
          Dollo parsimony assumes each domain was gained exactly once (at its lowest common
          ancestor node) and independently lost in any descendant lineage where it's absent.
          Divergence times from TimeTree molecular clock estimates.
        </p>
        {domain_events.length === 0 ? (
          <p className="text-xs text-gray-600 italic">No domain events computed (no domain annotations found).</p>
        ) : (
          <div className="space-y-1">
            {gainEvents.map((ev, i) => (
              <div key={i} className="flex items-start gap-2 text-xs">
                <span className="text-green-500 font-bold mt-0.5">+</span>
                <span className="text-gray-300">
                  <span className="text-green-400 font-mono">{ev.domain_id}</span>
                  {' '}gained at{' '}
                  <span className="text-blue-300">{ev.node_label}</span>
                  {ev.time_mya > 0 && <span className="text-gray-500"> (~{ev.time_mya} Mya)</span>}
                </span>
              </div>
            ))}
            {lossEvents.map((ev, i) => (
              <div key={i} className="flex items-start gap-2 text-xs">
                <span className="text-red-500 font-bold mt-0.5">−</span>
                <span className="text-gray-300">
                  <span className="text-red-400 font-mono">{ev.domain_id}</span>
                  {' '}lost in{' '}
                  <span className="text-orange-300">{ev.node_label}</span>
                  {ev.species && ev.species.length > 0 && (
                    <span className="text-gray-500"> ({ev.species.join(', ')})</span>
                  )}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Domain age legend */}
      <section>
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
          Domain Age Classification
        </h3>
        <div className="space-y-1 text-xs">
          {[
            ['#dc2626', 'Ancient (>3.5 Gya)', 'Present in E. coli (bacteria)'],
            ['#ea580c', 'Eukaryotic (~1.5 Gya)', 'Present in fungi and/or plants but not bacteria'],
            ['#ca8a04', 'Metazoan (~700 Mya)', 'Present in invertebrates (fly, worm)'],
            ['#16a34a', 'Vertebrate (~500 Mya)', 'Present in zebrafish or above'],
            ['#0d9488', 'Tetrapod (~360 Mya)', 'Present in frog, reptiles, birds, mammals'],
            ['#0284c7', 'Amniote (~300 Mya)', 'Present in reptiles/birds and/or mammals'],
            ['#7c3aed', 'Mammalian (~170 Mya)', 'Present in mouse, cow, human, chimp'],
            ['#c026d3', 'Primate (~6 Mya)', 'Present only in human and/or chimp'],
          ].map(([color, label, desc]) => (
            <div key={label} className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-sm flex-shrink-0" style={{ background: color }} />
              <span className="text-gray-300 font-medium">{label}</span>
              <span className="text-gray-600">— {desc}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
