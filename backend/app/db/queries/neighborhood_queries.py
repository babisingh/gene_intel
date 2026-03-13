"""
Cypher queries for gene neighborhood (CO_LOCATED_WITH) retrieval.
"""

from typing import Optional


def get_neighborhood(
    session,
    gene_id: str,
    max_distance_bp: int = 10000,
    limit: int = 50,
) -> Optional[dict]:
    """
    Fetch the focal gene and all CO_LOCATED_WITH neighbours
    within max_distance_bp.
    """
    # Get focal gene
    focal_result = session.run(
        """
        MATCH (g:Gene {gene_id: $gene_id})
        OPTIONAL MATCH (g)-[:HAS_DOMAIN]->(d:Domain)
        OPTIONAL MATCH (s:Species {taxon_id: g.species_taxon})
        RETURN g, collect(DISTINCT d.domain_id) AS domains, s.name AS species_name
        """,
        gene_id=gene_id,
    )
    focal_record = focal_result.single()
    if not focal_record:
        return None

    focal_gene_data = dict(focal_record["g"])
    focal_gene_data["domains"] = focal_record["domains"]
    focal_gene_data["species_name"] = focal_record["species_name"] or ""

    # Get neighbours
    neighbors_result = session.run(
        """
        MATCH (focal:Gene {gene_id: $gene_id})-[r:CO_LOCATED_WITH]-(n:Gene)
        WHERE r.distance_bp <= $max_distance_bp
        OPTIONAL MATCH (n)-[:HAS_DOMAIN]->(d:Domain)
        OPTIONAL MATCH (s:Species {taxon_id: n.species_taxon})
        RETURN n,
               collect(DISTINCT d.domain_id) AS domains,
               r.distance_bp AS distance_bp,
               s.name AS species_name
        LIMIT $limit
        """,
        gene_id=gene_id,
        max_distance_bp=max_distance_bp,
        limit=limit,
    )

    neighbours = []
    edges = []
    for rec in neighbors_result:
        n = dict(rec["n"])
        n["domains"] = rec["domains"]
        n["species_name"] = rec["species_name"] or ""
        neighbours.append(n)
        edges.append({
            "source": gene_id,
            "target": n["gene_id"],
            "type": "CO_LOCATED_WITH",
            "distance_bp": rec["distance_bp"],
        })

    return {
        "focal_gene": focal_gene_data,
        "neighbours": neighbours,
        "edges": edges,
    }
