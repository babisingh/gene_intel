"""
GET /api/neighborhood/{gene_id} — Returns focal gene + CO_LOCATED_WITH neighbours.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_neo4j_driver
from app.models.api_models import NeighborhoodResponse, GeneNode, GraphEdge
from app.db.queries.neighborhood_queries import get_neighborhood

router = APIRouter()


def _to_gene_node(raw: dict) -> GeneNode:
    return GeneNode(
        gene_id=raw.get("gene_id", ""),
        name=raw.get("name", ""),
        species_taxon=str(raw.get("species_taxon", "")),
        species_name=raw.get("species_name", ""),
        biotype=raw.get("biotype", "unknown"),
        cds_length=raw.get("cds_length"),
        exon_count=raw.get("exon_count"),
        utr_cds_ratio=raw.get("utr_cds_ratio"),
        chromosome=str(raw.get("chromosome", "")),
        start=raw.get("start", 0),
        end=raw.get("end", 0),
        domains=raw.get("domains", []),
    )


@router.get("/neighborhood/{gene_id}", response_model=NeighborhoodResponse)
def get_gene_neighborhood(
    gene_id: str,
    max_distance_bp: int = Query(default=10000, ge=0, le=100000),
    limit: int = Query(default=50, ge=1, le=300),
    driver=Depends(get_neo4j_driver),
):
    """Return the neighbourhood of a gene within max_distance_bp."""
    with driver.session() as session:
        result = get_neighborhood(session, gene_id, max_distance_bp, limit)

    if not result:
        raise HTTPException(status_code=404, detail=f"Gene not found: {gene_id}")

    focal = _to_gene_node(result["focal_gene"])
    neighbours = [_to_gene_node(n) for n in result["neighbours"]]
    edges = [
        GraphEdge(
            source=e["source"],
            target=e["target"],
            type=e["type"],
            distance_bp=e.get("distance_bp"),
        )
        for e in result["edges"]
    ]

    return NeighborhoodResponse(
        focal_gene=focal,
        neighbours=neighbours,
        edges=edges,
    )
