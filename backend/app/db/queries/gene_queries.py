"""
Pre-built Cypher queries for gene detail and species endpoints.
These are trusted internal queries — not user-generated.
"""

from typing import Optional


def get_gene_detail(session, gene_id: str) -> Optional[dict]:
    """Fetch full gene detail including transcripts, features, and domains."""
    result = session.run(
        """
        MATCH (g:Gene {gene_id: $gene_id})
        OPTIONAL MATCH (g)-[:HAS_TRANSCRIPT]->(t:Transcript)
        OPTIONAL MATCH (t)-[:HAS_FEATURE]->(f:Feature)
        OPTIONAL MATCH (g)-[:HAS_DOMAIN]->(d:Domain)
        OPTIONAL MATCH (s:Species {taxon_id: g.species_taxon})
        RETURN g,
               collect(DISTINCT t) AS transcripts,
               collect(DISTINCT f) AS features,
               collect(DISTINCT d.domain_id) AS domains,
               s.name AS species_name
        """,
        gene_id=gene_id,
    )
    record = result.single()
    if not record:
        return None

    g = dict(record["g"])
    return {
        "gene": g,
        "transcripts": [dict(t) for t in record["transcripts"] if t],
        "features": sorted(
            [dict(f) for f in record["features"] if f],
            key=lambda x: x.get("rank", 0),
        ),
        "domains": record["domains"],
        "species_name": record["species_name"] or "",
    }


def get_all_species(session) -> list:
    """Return all species with their gene counts."""
    result = session.run(
        """
        MATCH (s:Species)
        OPTIONAL MATCH (s)-[:HAS_GENE]->(g:Gene)
        RETURN s.taxon_id AS taxon_id,
               s.name AS name,
               s.common_name AS common_name,
               s.kingdom AS kingdom,
               count(g) AS gene_count
        ORDER BY s.name
        """
    )
    return [dict(r) for r in result]
