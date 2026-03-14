"""
GET /api/gene/{gene_id} — Returns full gene detail including features for locus diagram.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_neo4j_driver
from app.models.api_models import GeneDetailResponse, GeneNode
from app.db.queries.gene_queries import get_gene_detail
from app.agents.agent_c_explainer import explain_single_gene

router = APIRouter()


@router.get("/gene/{gene_id}", response_model=GeneDetailResponse)
def get_gene(
    gene_id: str,
    persona: str = "student",
    driver=Depends(get_neo4j_driver),
):
    """Return full gene detail including transcript features and Agent C explanation."""
    with driver.session() as session:
        detail = get_gene_detail(session, gene_id)

    if not detail:
        raise HTTPException(status_code=404, detail=f"Gene not found: {gene_id}")

    gene_data = detail["gene"]
    gene_data["domains"] = detail["domains"]
    gene_data["species_name"] = detail["species_name"]

    gene_node = GeneNode(
        gene_id=gene_data.get("gene_id", ""),
        name=gene_data.get("name", ""),
        species_taxon=str(gene_data.get("species_taxon", "")),
        species_name=detail["species_name"],
        biotype=gene_data.get("biotype", "unknown"),
        cds_length=gene_data.get("cds_length"),
        exon_count=gene_data.get("exon_count"),
        utr_cds_ratio=gene_data.get("utr_cds_ratio"),
        chromosome=str(gene_data.get("chromosome", "")),
        start=gene_data.get("start", 0),
        end=gene_data.get("end", 0),
        strand=gene_data.get("strand"),
        domains=detail["domains"],
    )

    # Generate explanation
    explanation = explain_single_gene(gene_data, persona=persona)

    return GeneDetailResponse(
        gene=gene_node,
        transcripts=detail["transcripts"],
        features=detail["features"],
        neighbours=[],  # Populated via /api/neighborhood/{gene_id}
        explanation=explanation,
    )
