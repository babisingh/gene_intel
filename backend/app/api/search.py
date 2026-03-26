"""
POST /api/search — Main NL query endpoint.

Flow: SearchRequest → Agent A (Cypher) → Neo4j → Agent C (explanation) → SearchResponse
"""

import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_neo4j_driver
from app.models.api_models import SearchRequest, SearchResponse, GeneNode, GraphEdge
from app.agents.graph_workflow import run_search

logger = logging.getLogger(__name__)
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
        strand=raw.get("strand"),
        domains=raw.get("domains", []),
    )


@router.post("/search", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    driver=Depends(get_neo4j_driver),
):
    """
    Convert a natural language genomic query into a graph result + explanation.
    """
    try:
        state = await run_search(
            nl_query=request.query,
            persona=request.persona,
            species_filter=request.species_filter,
            limit=request.limit,
            driver=driver,
        )
    except Exception as exc:
        logger.error("Search pipeline error: %s", exc)
        # Surface LLM/workflow failures as 422 (bad request) not 500 (server error)
        detail = str(exc)
        status = 422 if any(k in detail.lower() for k in ("refusal", "cypher", "llm", "query")) else 500
        raise HTTPException(status_code=status, detail=detail)

    if not state.get("success") and state.get("error"):
        raise HTTPException(status_code=422, detail=state["error"])

    nodes = [_to_gene_node(r) for r in state["raw_results"]]
    edges = [
        GraphEdge(
            source=e["source"],
            target=e["target"],
            type=e["type"],
            distance_bp=e.get("distance_bp"),
        )
        for e in state["edges"]
    ]

    return SearchResponse(
        query=request.query,
        cypher_used=state.get("cypher") if request.persona == "researcher" else None,
        nodes=nodes,
        edges=edges,
        explanation=state.get("explanation", ""),
        result_count=len(nodes),
    )
