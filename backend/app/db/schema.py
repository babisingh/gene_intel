"""
Neo4j schema initialisation for Gene-Intel.

Run once before first ingestion:
    python scripts/init_schema.py

Safe to re-run — all statements use IF NOT EXISTS guards.

How this connects to the rest of the app:
    - neo4j_client.py calls init_schema() during FastAPI lifespan startup
    - batch_writer.py relies on gene_id uniqueness constraint to MERGE safely
    - agent_a_semantic.py relies on the chromosome+start+end index for spatial queries
"""

CONSTRAINTS = [
    "CREATE CONSTRAINT species_taxon IF NOT EXISTS FOR (s:Species) REQUIRE s.taxon_id IS UNIQUE",
    "CREATE CONSTRAINT gene_id IF NOT EXISTS FOR (g:Gene) REQUIRE g.gene_id IS UNIQUE",
    "CREATE CONSTRAINT transcript_id IF NOT EXISTS FOR (t:Transcript) REQUIRE t.transcript_id IS UNIQUE",
    "CREATE CONSTRAINT feature_id IF NOT EXISTS FOR (f:Feature) REQUIRE f.feature_id IS UNIQUE",
    "CREATE CONSTRAINT domain_id IF NOT EXISTS FOR (d:Domain) REQUIRE d.domain_id IS UNIQUE",
]

INDEXES = [
    "CREATE INDEX gene_name IF NOT EXISTS FOR (g:Gene) ON (g.name)",
    "CREATE INDEX gene_biotype IF NOT EXISTS FOR (g:Gene) ON (g.biotype)",
    "CREATE INDEX gene_chromosome IF NOT EXISTS FOR (g:Gene) ON (g.chromosome, g.start, g.end)",
    "CREATE INDEX gene_cds_length IF NOT EXISTS FOR (g:Gene) ON (g.cds_length)",
    "CREATE INDEX gene_utr_ratio IF NOT EXISTS FOR (g:Gene) ON (g.utr_cds_ratio)",
    "CREATE INDEX gene_species IF NOT EXISTS FOR (g:Gene) ON (g.species_taxon)",
    "CREATE INDEX feature_type IF NOT EXISTS FOR (f:Feature) ON (f.type)",
    "CREATE INDEX domain_source IF NOT EXISTS FOR (d:Domain) ON (d.source, d.domain_id)",
    "CREATE INDEX coloc_distance IF NOT EXISTS FOR ()-[r:CO_LOCATED_WITH]-() ON (r.distance_bp)",
]


def init_schema(driver) -> None:
    """Apply all constraints and indexes. Safe to run multiple times."""
    with driver.session() as session:
        for stmt in CONSTRAINTS + INDEXES:
            session.run(stmt)
