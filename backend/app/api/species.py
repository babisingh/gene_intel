"""
GET /api/species — Returns all loaded species with gene counts.
"""

from fastapi import APIRouter, Depends
from typing import List

from app.dependencies import get_neo4j_driver
from app.models.api_models import SpeciesInfo
from app.db.queries.gene_queries import get_all_species

router = APIRouter()


@router.get("/species", response_model=List[SpeciesInfo])
def list_species(driver=Depends(get_neo4j_driver)):
    """Return all species with their gene counts."""
    with driver.session() as session:
        rows = get_all_species(session)

    return [
        SpeciesInfo(
            taxon_id=r["taxon_id"] or "",
            name=r["name"] or "",
            common_name=r["common_name"] or "",
            kingdom=r["kingdom"] or "",
            gene_count=r["gene_count"] or 0,
        )
        for r in rows
    ]
