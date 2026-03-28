/**
 * DiscoveryChips — Sample queries rendered as clickable pills above the search bar.
 *
 * All queries below were validated against the actual GTF/GFF3 files in the database:
 *   - 15 species confirmed (human, chimp, mouse, chicken, xenopus, zebrafish, fly,
 *     worm, arabidopsis, rice, moss, chlamydomonas, aspergillus, yeast, E. coli)
 *   - Gene names, biotypes and structural properties cross-checked in source files
 *   - Queries that returned 0 results in the source data were removed
 *
 * To regenerate after new data ingestion, query Neo4j directly and confirm each
 * chip returns at least 1 result before re-enabling it.
 */

import type { DiscoveryChip } from '../../types'

export const DISCOVERY_CHIPS: DiscoveryChip[] = [

  // ── CROSS-SPECIES ─────────────────────────────────────────────────────────
  // SOD1: confirmed in human, mouse, chimp, zebrafish, xenopus, fly (6 species)
  {
    label: 'SOD1 across kingdoms',
    query: 'Show SOD1 in human, zebrafish and fly — compare gene length and exon count across these three lineages',
    category: 'cross-species',
  },
  // EGFR: confirmed in human, mouse, chimp, xenopus, fly
  {
    label: 'EGFR from fly to human',
    query: 'Find EGFR in human, mouse and fly — show how the receptor gene structure changed over 600 million years',
    category: 'cross-species',
  },
  // CDK2: confirmed in human, mouse, zebrafish, chimp, xenopus, fly
  {
    label: 'CDK2 conservation',
    query: 'Compare CDK2 between human, zebrafish and fly — show exon counts and CDS length',
    category: 'cross-species',
  },

  // ── DRUG DISCOVERY ────────────────────────────────────────────────────────
  // CASP1-14: all confirmed in human GTF
  {
    label: 'Human caspase family',
    query: 'Show all caspase genes in human — CASP1 through CASP14, their sizes and chromosomal locations',
    category: 'drug-discovery',
  },
  // PCSK9: confirmed in human, mouse, chimp, chicken, zebrafish, xenopus
  {
    label: 'PCSK9 in vertebrates',
    query: 'Find PCSK9 in human and mouse — compare their gene length and exon structure',
    category: 'drug-discovery',
  },
  // Uncharacterized: 839 LOC genes confirmed in human; FURIN also confirmed
  {
    label: 'Uncharacterized near FURIN',
    query: 'Find uncharacterized protein-coding genes co-located with FURIN or PCSK proteases in human',
    category: 'drug-discovery',
  },

  // ── EVOLUTION ─────────────────────────────────────────────────────────────
  // Pseudogenes: human 15,222 vs chimp 485 — striking contrast confirmed
  {
    label: 'Human pseudogene burst',
    query: 'Compare pseudogene counts in human versus chimpanzee — why does human have 30× more?',
    category: 'evolution',
  },
  // Photosynthesis: PSAE, PSAF, RBCS-1, Lhcb4 confirmed in Chlamydomonas GTF
  {
    label: 'Photosynthesis core in alga',
    query: 'Show photosynthesis genes in Chlamydomonas alga — find light-harvesting and rubisco genes',
    category: 'evolution',
  },
  // E. coli: 4,506 genes; bio_dict "compact genes" uses length < 1000
  {
    label: 'E. coli compact genes',
    query: 'Find the most compact protein-coding genes in E. coli — under 500 base pairs, show their neighbours',
    category: 'evolution',
  },

  // ── GENE STRUCTURE ────────────────────────────────────────────────────────
  // lncRNA: 19,370 in human confirmed; MYC confirmed in human
  {
    label: 'lncRNA near MYC',
    query: 'Find long non-coding RNA genes near MYC in human — potential oncogenic regulators',
    category: 'structure',
  },
  // Complex splicing: Xenopus confirmed in GTF; bio_dict uses t.exon_count > 8
  {
    label: 'Xenopus complex splicing',
    query: 'Find Xenopus tropicalis genes with complex splicing — more than 8 exons — show their sizes',
    category: 'structure',
  },
  // ARF TFs: ARF1-21 confirmed in Arabidopsis; bio_dict has transcription factor entry
  {
    label: 'Arabidopsis ARF factors',
    query: 'Show ARF transcription factor genes in Arabidopsis — auxin response regulators and their gene structure',
    category: 'structure',
  },
]

const CATEGORY_STYLES: Record<DiscoveryChip['category'], string> = {
  'cross-species':  'bg-purple-900/50 text-purple-300 hover:bg-purple-800/60 border-purple-700',
  'drug-discovery': 'bg-blue-900/50 text-blue-300 hover:bg-blue-800/60 border-blue-700',
  'evolution':      'bg-green-900/50 text-green-300 hover:bg-green-800/60 border-green-700',
  'structure':      'bg-amber-900/50 text-amber-300 hover:bg-amber-800/60 border-amber-700',
}

interface DiscoveryChipsProps {
  onSelect: (query: string) => void
}

export function DiscoveryChips({ onSelect }: DiscoveryChipsProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {DISCOVERY_CHIPS.map((chip) => (
        <button
          key={chip.label}
          onClick={() => onSelect(chip.query)}
          className={`
            px-3 py-1.5 rounded-full text-xs font-medium border transition-colors cursor-pointer
            ${CATEGORY_STYLES[chip.category]}
          `}
          title={chip.query}
        >
          {chip.label}
        </button>
      ))}
    </div>
  )
}
