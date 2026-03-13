"""
Batched Neo4j writer using UNWIND for performance.

Why UNWIND matters:
  Inserting 30,000 genes one-by-one in individual transactions takes ~10 minutes.
  UNWIND batches 1,000 nodes into a single transaction — the same load takes ~30 seconds.

ELI15: Instead of mailing 1,000 letters one at a time, we pack them into batches of 1,000
and deliver each batch in a single trip to the post office.

MERGE is used instead of CREATE so the script is safely re-runnable — re-ingesting a
species updates properties without creating duplicates.

Connected to:
  - run_ingest.py: calls write_genes_batch(), write_transcripts_batch(), write_edges_batch()
  - schema.py: relies on uniqueness constraints to make MERGE efficient
"""

from typing import List, Dict
import os

BATCH_SIZE = int(os.getenv("INGEST_BATCH_SIZE", 1000))


def chunked(lst: List, size: int):
    """Split list into chunks of at most `size` items."""
    for i in range(0, len(lst), size):
        yield lst[i: i + size]


def write_species_node(session, species: Dict):
    """MERGE a single :Species node."""
    session.run(
        """
        MERGE (s:Species {taxon_id: $taxon_id})
        SET s += $props
        """,
        taxon_id=species["taxon_id"],
        props=species,
    )


def write_genes_batch(session, genes: List[Dict]):
    """MERGE :Gene nodes in batches. Updates all properties on re-ingest."""
    query = """
    UNWIND $batch AS row
    MERGE (g:Gene {gene_id: row.gene_id})
    SET g += row
    WITH g, row
    MATCH (s:Species {taxon_id: row.species_taxon})
    MERGE (s)-[:HAS_GENE]->(g)
    """
    for chunk in chunked(genes, BATCH_SIZE):
        session.run(query, batch=chunk)


def write_transcripts_batch(session, transcripts: List[Dict]):
    query = """
    UNWIND $batch AS row
    MERGE (t:Transcript {transcript_id: row.transcript_id})
    SET t += row
    WITH t, row
    MATCH (g:Gene {gene_id: row.gene_id})
    MERGE (g)-[:HAS_TRANSCRIPT]->(t)
    """
    for chunk in chunked(transcripts, BATCH_SIZE):
        session.run(query, batch=chunk)


def write_features_batch(session, features: List[Dict]):
    query = """
    UNWIND $batch AS row
    MERGE (f:Feature {feature_id: row.feature_id})
    SET f += row
    WITH f, row
    MATCH (t:Transcript {transcript_id: row.transcript_id})
    MERGE (t)-[:HAS_FEATURE]->(f)
    """
    for chunk in chunked(features, BATCH_SIZE):
        session.run(query, batch=chunk)


def write_domains_batch(session, gene_domains: List[Dict]):
    """
    Creates :Domain nodes and HAS_DOMAIN edges.
    gene_domains items: {gene_id, domain_id, source, description}
    """
    query = """
    UNWIND $batch AS row
    MERGE (d:Domain {domain_id: row.domain_id})
    SET d.source = row.source, d.description = row.description
    WITH d, row
    MATCH (g:Gene {gene_id: row.gene_id})
    MERGE (g)-[:HAS_DOMAIN]->(d)
    """
    for chunk in chunked(gene_domains, BATCH_SIZE):
        session.run(query, batch=chunk)


def write_edges_batch(session, edges: List[Dict]):
    """
    Creates CO_LOCATED_WITH edges between neighbouring genes.
    edges items: {from_id, to_id, distance_bp}
    """
    query = """
    UNWIND $batch AS row
    MATCH (a:Gene {gene_id: row.from_id})
    MATCH (b:Gene {gene_id: row.to_id})
    MERGE (a)-[r:CO_LOCATED_WITH]-(b)
    SET r.distance_bp = row.distance_bp
    """
    for chunk in chunked(edges, BATCH_SIZE):
        session.run(query, batch=chunk)
