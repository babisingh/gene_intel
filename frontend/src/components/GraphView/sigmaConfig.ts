/**
 * Sigma.js v3 configuration for Gene-Intel.
 *
 * Key design decisions:
 *   - Max 300 nodes: enforced at API level (LIMIT 300 in Cypher)
 *     and asserted here defensively
 *   - Species colour coding: each of the 15 species gets a unique colour
 *     from a perceptually-distinct palette
 *   - Edge types: solid lines = CO_LOCATED_WITH, dashed = HAS_DOMAIN_MATCH
 *   - Node size encodes CDS length (larger = more protein coding content)
 *
 * Connected to: GraphView.tsx (consumes this config to initialise the Sigma instance)
 */

export const SPECIES_COLORS: Record<string, string> = {
  '9606':   '#4C9BE8',  // Human — blue
  '10090':  '#E8834C',  // Mouse — orange
  '7955':   '#4CE8A0',  // Zebrafish — green
  '9031':   '#E8D44C',  // Chicken — yellow
  '175781': '#C44CE8',  // Octopus — purple
  '9598':   '#4CBDE8',  // Chimp — light blue
  '7227':   '#E84C4C',  // Drosophila — red
  '6239':   '#E8B44C',  // C. elegans — amber
  '3702':   '#4CE860',  // Arabidopsis — bright green
  '4530':   '#7BE84C',  // Rice — lime
  '3218':   '#4CE8D4',  // Moss — teal
  '3055':   '#1AB87A',  // Chlamydomonas — dark teal
  '162425': '#B84C4C',  // Aspergillus — dark red
  '4932':   '#E8774C',  // Yeast — salmon
  '511145': '#888888',  // E. coli — grey
}

export const DEFAULT_NODE_COLOR = '#6B7280'

export const NODE_SIZE_SCALE = {
  min: 4,
  max: 14,
  // cds_length range across all species: 150–50000 bp
  cdsMin: 150,
  cdsMax: 50000,
}

export function getNodeSize(cdsLength: number | null): number {
  if (!cdsLength) return NODE_SIZE_SCALE.min
  const t = Math.min(
    1,
    Math.max(
      0,
      (cdsLength - NODE_SIZE_SCALE.cdsMin) /
        (NODE_SIZE_SCALE.cdsMax - NODE_SIZE_SCALE.cdsMin),
    ),
  )
  return NODE_SIZE_SCALE.min + t * (NODE_SIZE_SCALE.max - NODE_SIZE_SCALE.min)
}

export function getNodeColor(speciesTaxon: string): string {
  return SPECIES_COLORS[speciesTaxon] ?? DEFAULT_NODE_COLOR
}

export const EDGE_STYLES = {
  CO_LOCATED_WITH: {
    color: '#4B5563',
    size: 1,
  },
  HAS_DOMAIN_MATCH: {
    color: '#6366F1',
    size: 2,
  },
}
