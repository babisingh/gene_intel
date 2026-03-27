// Core domain types — mirrors the backend Pydantic models

export interface GeneNode {
  gene_id: string
  name: string
  species_taxon: string
  species_name: string
  biotype: string
  cds_length: number | null
  exon_count: number | null
  utr_cds_ratio: number | null
  chromosome: string
  start: number
  end: number
  strand: '+' | '-' | null
  domains: string[]
}

export interface GraphEdge {
  source: string
  target: string
  type: 'CO_LOCATED_WITH' | 'HAS_DOMAIN_MATCH'
  distance_bp: number | null
}

export interface SearchRequest {
  query: string
  persona: Persona
  species_filter: string[] | null
  limit: number
}

export interface SearchResponse {
  query: string
  cypher_used: string | null
  nodes: GeneNode[]
  edges: GraphEdge[]
  explanation: string
  result_count: number
}

export interface SpeciesInfo {
  taxon_id: string
  name: string
  common_name: string
  kingdom: string
  gene_count: number
}

export interface FeatureRecord {
  feature_id: string
  transcript_id: string
  type: 'CDS' | 'exon' | 'UTR' | 'start_codon' | 'stop_codon'
  length: number
  rank: number
  start: number
  end: number
}

export interface TranscriptRecord {
  transcript_id: string
  type: string
  exon_count: number
  support_level: number | null
  is_canonical: boolean
}

export interface GeneDetailResponse {
  gene: GeneNode
  transcripts: TranscriptRecord[]
  features: FeatureRecord[]
  neighbours: GeneNode[]
  explanation: string
}

export interface NeighborhoodResponse {
  focal_gene: GeneNode
  neighbours: GeneNode[]
  edges: GraphEdge[]
}

export interface HealthResponse {
  neo4j: 'ok' | 'error'
  llm: 'ok' | 'error'
  species_loaded: number
}

export interface IngestStatusResponse {
  status: 'idle' | 'running' | 'complete' | 'error'
  species: string | null
  progress: string | null
  error: string | null
}

export type Persona = 'researcher'

export interface DiscoveryChip {
  label: string
  query: string
  category: 'cross-species' | 'drug-discovery' | 'evolution' | 'structure'
}
