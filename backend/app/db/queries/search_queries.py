"""
Executes Agent A-generated Cypher queries against Neo4j.
Results are normalised into GeneNode-compatible dicts.
"""

from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

# Taxon ID → species name cache (avoids repeated lookups)
_species_name_cache: dict[str, str] = {}


def _get_species_name(session, taxon_id: str) -> str:
    if taxon_id in _species_name_cache:
        return _species_name_cache[taxon_id]
    result = session.run(
        "MATCH (s:Species {taxon_id: $tid}) RETURN s.name AS name",
        tid=taxon_id,
    )
    record = result.single()
    name = record["name"] if record else taxon_id
    _species_name_cache[taxon_id] = name
    return name


def execute_search_cypher(
    session,
    cypher: str,
    species_name_lookup: Optional[dict] = None,
) -> List[dict]:
    """
    Execute validated Cypher and return list of gene result dicts.

    Expected Cypher return shape (as specified in Agent A prompt):
        RETURN g as gene, collect(DISTINCT d.domain_id) as domains, g.species_taxon as species
    """
    results = []
    try:
        records = session.run(cypher)
        for record in records:
            gene = dict(record.get("gene", record.get("g", {})))
            domains = list(record.get("domains", []))
            taxon = record.get("species", gene.get("species_taxon", ""))

            species_name = ""
            if species_name_lookup:
                species_name = species_name_lookup.get(str(taxon), str(taxon))
            else:
                species_name = _get_species_name(session, str(taxon))

            gene["domains"] = domains
            gene["species_name"] = species_name
            gene.setdefault("species_taxon", str(taxon))
            results.append(gene)
    except Exception as exc:
        logger.error("Cypher execution error: %s | Query: %s", exc, cypher)
        raise

    return results


def build_edges_from_results(session, gene_ids: List[str]) -> List[dict]:
    """
    Given a list of gene_ids returned by a search, fetch CO_LOCATED_WITH
    edges between them to populate the graph view.
    """
    if len(gene_ids) < 2:
        return []

    result = session.run(
        """
        MATCH (a:Gene)-[r:CO_LOCATED_WITH]-(b:Gene)
        WHERE a.gene_id IN $ids AND b.gene_id IN $ids
        RETURN a.gene_id AS source, b.gene_id AS target, r.distance_bp AS distance_bp
        LIMIT 1000
        """,
        ids=gene_ids,
    )

    seen = set()
    edges = []
    for rec in result:
        key = tuple(sorted([rec["source"], rec["target"]]))
        if key not in seen:
            seen.add(key)
            edges.append({
                "source": rec["source"],
                "target": rec["target"],
                "type": "CO_LOCATED_WITH",
                "distance_bp": rec["distance_bp"],
            })
    return edges
