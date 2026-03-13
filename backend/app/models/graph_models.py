"""
Python dataclasses mirroring Neo4j graph nodes.
Used internally by ingestion and query layers.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SpeciesNode:
    taxon_id: str
    name: str
    common_name: str
    assembly: str
    kingdom: str
    gtf_source: str          # "ensembl" | "ncbi_gff3"
    ingested_at: Optional[str] = None


@dataclass
class GeneNode:
    gene_id: str
    name: str
    biotype: str
    chromosome: str
    start: int
    end: int
    strand: str
    length: int
    species_taxon: str
    cds_length: int = 0
    exon_count: int = 0
    utr5_length: int = 0
    utr3_length: int = 0
    utr_cds_ratio: Optional[float] = None


@dataclass
class TranscriptNode:
    transcript_id: str
    gene_id: str             # FK to GeneNode
    type: str                # "mRNA" | "lncRNA" | "ncRNA"
    exon_count: int = 0
    support_level: Optional[int] = None
    is_canonical: bool = False


@dataclass
class FeatureNode:
    feature_id: str          # "{transcript_id}_{type}_{rank}"
    transcript_id: str       # FK to TranscriptNode
    type: str                # "CDS" | "exon" | "UTR" | "start_codon" | "stop_codon"
    length: int
    rank: int
    start: int
    end: int


@dataclass
class DomainNode:
    domain_id: str           # e.g. "Pfam:PF00082"
    source: str              # "Pfam" | "InterPro" | "GO" | "KEGG"
    description: str = ""


@dataclass
class CoLocatedEdge:
    from_id: str             # gene_id
    to_id: str               # gene_id
    distance_bp: int
