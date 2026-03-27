"""
GET /api/evolution/{gene_name}
Returns evolutionary profile for a gene family across all 17 species.

Response includes:
  gene_name        : searched symbol
  species_count    : how many species the gene was found in
  species_profiles : per-species structural data (exons, UTR, domains, etc.)
  domain_matrix    : domain presence/absence per species
  domain_ages      : age classification per domain (Dollo parsimony LCA)
  domain_events    : gain/loss events annotated on phylogenetic tree
  narrative        : LLM-generated evolutionary narrative (markdown)
  phylo_tree       : tree topology for frontend SVG rendering
  species_meta     : display metadata for each taxon
  species_order    : phylogenetic leaf ordering
"""

import logging
from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_neo4j_driver
from app.db.queries.evolution_queries import get_gene_family_profiles, get_domain_descriptions
from app.evolution.phylo_tree import (
    classify_domain_age,
    compute_domain_events,
    tree_for_frontend,
    SPECIES_ORDER,
    SPECIES_META,
    PHYLO_TREE,
)
from app.agents.agent_evo import generate_evolutionary_narrative

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/evolution/{gene_name}")
def get_evolution(gene_name: str, driver=Depends(get_neo4j_driver)):
    with driver.session() as session:
        profiles = get_gene_family_profiles(session, gene_name)
        domain_ids_all: list[str] = []  # populated after dedup below

    if not profiles:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No genes named '{gene_name}' found across any of the 17 species. "
                "Try an exact gene symbol such as TP53, BRCA1, GAPDH, SOD1, or EGFR."
            ),
        )

    # Deduplicate paralogs per species: keep the one with the most domain annotations
    best: dict[str, dict] = {}
    for p in profiles:
        tid = p["taxon_id"]
        if tid not in best or len(p.get("domains") or []) > len(best[tid].get("domains") or []):
            best[tid] = p
    profiles = list(best.values())

    # Sort by canonical phylogenetic order
    order_idx = {t: i for i, t in enumerate(SPECIES_ORDER)}
    profiles.sort(key=lambda p: order_idx.get(p["taxon_id"], 99))

    # Build domain presence matrix
    domain_to_taxa: dict[str, set] = {}
    for p in profiles:
        for d in p.get("domains") or []:
            domain_to_taxa.setdefault(d, set()).add(p["taxon_id"])

    # Fetch descriptions for all domain IDs from Neo4j
    all_domain_ids = list(domain_to_taxa.keys())
    with driver.session() as session:
        domain_descriptions = get_domain_descriptions(session, all_domain_ids)

    # Classify domain ages
    domain_ages = [
        {
            "domain_id": d,
            "taxon_ids_present": sorted(t),
            "species_present": [SPECIES_META.get(x, {}).get("short", x) for x in sorted(t)],
            "age": classify_domain_age(t),
        }
        for d, t in domain_to_taxa.items()
    ]
    domain_ages.sort(key=lambda x: -x["age"]["time_mya"])

    # Compute gain/loss events via Dollo parsimony
    domain_events: list[dict] = []
    for d, taxa in domain_to_taxa.items():
        domain_events.extend(compute_domain_events(d, taxa))

    # LLM narrative (may take ~15s)
    try:
        narrative = generate_evolutionary_narrative(
            gene_name, profiles, domain_events, domain_ages
        )
    except Exception as e:
        logger.error("Narrative generation failed: %s", e)
        narrative = f"*Narrative generation failed: {e}*"

    # Enrich domain_ages and domain_events with description/source/display_id
    def _enrich(d: str) -> dict:
        info = domain_descriptions.get(d, {})
        return {
            "description": info.get("description", ""),
            "source": info.get("source", ""),
            "display_id": info.get("display_id", d),
        }

    for da in domain_ages:
        da.update(_enrich(da["domain_id"]))

    for ev in domain_events:
        ev.update(_enrich(ev["domain_id"]))

    return {
        "gene_name": gene_name,
        "species_count": len(profiles),
        "species_profiles": profiles,
        "domain_matrix": [
            {
                "domain_id": d,
                "taxon_ids_present": sorted(t),
                "species_present": [SPECIES_META.get(x, {}).get("short", x) for x in sorted(t)],
                **_enrich(d),
            }
            for d, t in sorted(domain_to_taxa.items())
        ],
        "domain_ages": domain_ages,
        "domain_events": domain_events,
        "domain_descriptions": domain_descriptions,
        "narrative": narrative,
        "phylo_tree": tree_for_frontend(PHYLO_TREE),
        "species_meta": SPECIES_META,
        "species_order": SPECIES_ORDER,
    }
