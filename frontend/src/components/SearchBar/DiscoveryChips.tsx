/**
 * DiscoveryChips — Sample queries rendered as clickable pills above the search bar.
 * Primary onboarding mechanism for new users.
 */

import type { DiscoveryChip } from '../../types'

export const DISCOVERY_CHIPS: DiscoveryChip[] = [
  // ── CROSS-SPECIES FUNCTIONAL TWINS ──
  {
    label: 'GLP-1 functional twins',
    query: 'Find functional twins of GLP-1 with glucagon domains near a protease in all species',
    category: 'cross-species',
  },
  {
    label: 'Insulin structural twins',
    query: 'Find structural twins of insulin across plants, fungi and animals',
    category: 'cross-species',
  },
  {
    label: 'Human vs chimp kinases',
    query: 'Compare kinase genes between human and chimpanzee — show differences',
    category: 'cross-species',
  },

  // ── DRUG DISCOVERY ──
  {
    label: 'Drug-like peptides near proteases',
    query: 'Find drug-like peptides co-located with cutting enzymes across all species',
    category: 'drug-discovery',
  },
  {
    label: 'Novel protease targets',
    query: 'Show uncharacterized genes with protease domains in zebrafish and human',
    category: 'drug-discovery',
  },
  {
    label: 'Bacterial enzyme diversity',
    query: 'Find all unique metabolic enzyme domains in E. coli not found in yeast',
    category: 'drug-discovery',
  },

  // ── EVOLUTION ──
  {
    label: 'Most conserved neighbourhoods',
    query: 'Which species has the most conserved gene neighbourhood for pigment genes?',
    category: 'evolution',
  },
  {
    label: 'Photosynthesis across kingdoms',
    query: 'Compare photosynthesis genes between green alga, moss and rice',
    category: 'evolution',
  },
  {
    label: 'Complex splicing champions',
    query: 'Which species has the most genes with over 10 exons?',
    category: 'evolution',
  },

  // ── GENE STRUCTURE ──
  {
    label: 'UTR-heavy regulators',
    query: 'Find UTR-heavy genes near transcription factors in Arabidopsis',
    category: 'structure',
  },
  {
    label: 'Bacterial compact genes',
    query: 'Show compact genes under 500bp in E. coli with metabolic domains',
    category: 'structure',
  },
  {
    label: 'Xenopus splicing complexity',
    query: 'Find Xenopus tropicalis genes with complex splicing near neurotransmitter domains',
    category: 'structure',
  },
]

const CATEGORY_STYLES: Record<DiscoveryChip['category'], string> = {
  'cross-species': 'bg-purple-900/50 text-purple-300 hover:bg-purple-800/60 border-purple-700',
  'drug-discovery': 'bg-blue-900/50 text-blue-300 hover:bg-blue-800/60 border-blue-700',
  'evolution': 'bg-green-900/50 text-green-300 hover:bg-green-800/60 border-green-700',
  'structure': 'bg-amber-900/50 text-amber-300 hover:bg-amber-800/60 border-amber-700',
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
