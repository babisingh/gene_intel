"""
Pydantic request/response models for the Gene-Intel API.
Used by FastAPI for automatic validation and OpenAPI schema generation.
"""

from pydantic import BaseModel
from typing import List, Optional


class SearchRequest(BaseModel):
    query: str                           # Natural language query
    persona: str = "student"             # "business" | "student" | "researcher"
    species_filter: Optional[List[str]] = None  # List of taxon_ids to restrict to
    limit: int = 300


class GeneNode(BaseModel):
    gene_id: str
    name: str
    species_taxon: str
    species_name: str
    biotype: str
    cds_length: Optional[int] = None
    exon_count: Optional[int] = None
    utr_cds_ratio: Optional[float] = None
    chromosome: str
    start: int
    end: int
    strand: Optional[str] = None         # "+" | "-" | None
    domains: List[str]                   # List of domain_id strings


class GraphEdge(BaseModel):
    source: str                          # gene_id
    target: str                          # gene_id
    type: str                            # "CO_LOCATED_WITH" | "HAS_DOMAIN_MATCH"
    distance_bp: Optional[int] = None


class SearchResponse(BaseModel):
    query: str
    cypher_used: Optional[str] = None    # Shown in researcher persona only
    nodes: List[GeneNode]
    edges: List[GraphEdge]
    explanation: str                     # Agent C output
    result_count: int


class GeneDetailResponse(BaseModel):
    gene: GeneNode
    transcripts: list
    features: list                       # For gene locus diagram
    neighbours: List[GeneNode]           # CO_LOCATED_WITH genes
    explanation: str                     # Agent C explanation of this single gene


class SpeciesInfo(BaseModel):
    taxon_id: str
    name: str
    common_name: str
    kingdom: str
    gene_count: int


class NeighborhoodResponse(BaseModel):
    focal_gene: GeneNode
    neighbours: List[GeneNode]
    edges: List[GraphEdge]


class HealthResponse(BaseModel):
    neo4j: str          # "ok" | "error"
    llm: str            # "ok" | "error"
    species_loaded: int


class IngestStatusResponse(BaseModel):
    status: str         # "idle" | "running" | "complete" | "error"
    species: Optional[str] = None
    progress: Optional[str] = None
    error: Optional[str] = None
