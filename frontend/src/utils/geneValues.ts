import type { GeneNode } from '../types'

const SOURCE_LABELS = {
  Ensembl_canonical: 'canonical transcript',
  longest_cds: 'transcript with the longest CDS',
  longest_transcript: 'longest transcript',
} as const

/**
 * Which transcript a gene's CDS length, exon count and UTR/CDS ratio
 * describe, as a short label, or null for a gene without transcripts.
 * A graph built before canonical_source existed sums every transcript.
 */
export function geneValuesBasis(gene: GeneNode): string | null {
  if (gene.canonical_source) return SOURCE_LABELS[gene.canonical_source]
  return gene.exon_count ? 'summed over all transcripts' : null
}
