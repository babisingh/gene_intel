// Types for the evolutionary analysis endpoint (/api/evolution/{gene_name})

export interface SpeciesProfile {
  gene_id: string
  gene_name: string
  biotype: string
  exon_count: number | null
  cds_length: number | null
  utr_cds_ratio: number | null
  utr5_length: number | null
  utr3_length: number | null
  chromosome: string
  start: number
  end: number
  strand: string | null
  taxon_id: string
  species_name: string
  common_name: string
  assembly: string
  domains: string[]
  transcript_count: number
}

export interface DomainMatrixEntry {
  domain_id: string
  taxon_ids_present: string[]
  species_present: string[]
}

export interface DomainAge {
  domain_id: string
  taxon_ids_present: string[]
  species_present: string[]
  age: { label: string; time_mya: number }
}

export interface DomainEvent {
  type: 'gain' | 'loss'
  domain_id: string
  node: string
  node_label: string
  time_mya: number
  species?: string[]  // only for loss events
}

export interface PhyloNode {
  name: string
  label: string
  time_mya: number
  taxon_id?: string
  children?: PhyloNode[]
}

export interface SpeciesMeta {
  common: string
  short: string
  kingdom: string
}

export interface EvolutionResponse {
  gene_name: string
  species_count: number
  species_profiles: SpeciesProfile[]
  domain_matrix: DomainMatrixEntry[]
  domain_ages: DomainAge[]
  domain_events: DomainEvent[]
  narrative: string
  phylo_tree: PhyloNode
  species_meta: Record<string, SpeciesMeta>
  species_order: string[]
}
