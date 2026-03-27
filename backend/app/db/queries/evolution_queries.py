"""
Neo4j queries for cross-species evolutionary analysis.
Used by the /api/evolution/{gene_name} endpoint.
"""


def get_gene_family_profiles(session, gene_name: str) -> list[dict]:
    """
    Fetch all genes matching gene_name (case-insensitive) across all species,
    with domain annotations and structural metrics.
    Returns one dict per gene instance found.
    """
    result = session.run(
        """
        MATCH (s:Species)-[:HAS_GENE]->(g:Gene)
        WHERE toLower(g.name) = toLower($name)
        OPTIONAL MATCH (g)-[:HAS_DOMAIN]->(d:Domain)
        OPTIONAL MATCH (g)-[:HAS_TRANSCRIPT]->(t:Transcript)
        WITH g, s,
             collect(DISTINCT d.domain_id) AS domains,
             count(DISTINCT t) AS transcript_count
        RETURN
            g.gene_id         AS gene_id,
            g.name            AS gene_name,
            g.biotype         AS biotype,
            g.exon_count      AS exon_count,
            g.cds_length      AS cds_length,
            g.utr_cds_ratio   AS utr_cds_ratio,
            g.utr5_length     AS utr5_length,
            g.utr3_length     AS utr3_length,
            g.chromosome      AS chromosome,
            g.start           AS start,
            g.end             AS end,
            g.strand          AS strand,
            s.taxon_id        AS taxon_id,
            s.name            AS species_name,
            s.common_name     AS common_name,
            s.assembly        AS assembly,
            domains,
            transcript_count
        ORDER BY s.name
        """,
        name=gene_name,
    )
    return [dict(r) for r in result]
