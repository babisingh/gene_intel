"""
Tests for cypher_validator.py
"""

from app.agents.cypher_validator import validate_cypher


# ── Valid queries ────────────────────────────────────────────────────────────

def test_valid_simple_query():
    cypher = """
    MATCH (g:Gene)
    WHERE g.biotype = 'protein_coding'
    RETURN g as gene, collect(DISTINCT d.domain_id) as domains, g.species_taxon as species
    LIMIT 300
    """
    result = validate_cypher(cypher)
    assert result["valid"] is True


def test_valid_query_with_domain_match():
    cypher = """
    MATCH (g:Gene)-[:HAS_DOMAIN]->(d:Domain)
    WHERE d.domain_id = 'Pfam:PF00069'
    RETURN g as gene, collect(DISTINCT d.domain_id) as domains, g.species_taxon as species
    LIMIT 300
    """
    result = validate_cypher(cypher)
    assert result["valid"] is True


# ── Missing clauses ──────────────────────────────────────────────────────────

def test_missing_return_fails():
    cypher = "MATCH (g:Gene) WHERE g.biotype = 'protein_coding' LIMIT 300"
    result = validate_cypher(cypher)
    assert result["valid"] is False
    assert "RETURN" in result["error"]


def test_missing_limit_fails():
    cypher = "MATCH (g:Gene) RETURN g"
    result = validate_cypher(cypher)
    assert result["valid"] is False
    assert "LIMIT" in result["error"]


# ── Destructive operations ────────────────────────────────────────────────────

def test_delete_blocked():
    cypher = "MATCH (g:Gene) DELETE g"
    result = validate_cypher(cypher)
    assert result["valid"] is False


def test_drop_blocked():
    cypher = "DROP INDEX gene_name"
    result = validate_cypher(cypher)
    assert result["valid"] is False


def test_create_blocked():
    cypher = "CREATE (g:Gene {gene_id: 'fake'}) RETURN g LIMIT 1"
    result = validate_cypher(cypher)
    assert result["valid"] is False


def test_merge_blocked():
    cypher = "MERGE (g:Gene {gene_id: 'fake'}) RETURN g LIMIT 1"
    result = validate_cypher(cypher)
    assert result["valid"] is False


# ── Label whitelist ───────────────────────────────────────────────────────────

def test_unknown_label_fails():
    cypher = """
    MATCH (g:Gene)-[:HAS_DOMAIN]->(p:Protein)
    RETURN g, p LIMIT 10
    """
    result = validate_cypher(cypher)
    assert result["valid"] is False
    assert "Protein" in result["error"]


# ── Property whitelist ────────────────────────────────────────────────────────

def test_unknown_property_fails():
    cypher = """
    MATCH (g:Gene)
    WHERE g.sequence_length > 1000
    RETURN g LIMIT 10
    """
    result = validate_cypher(cypher)
    assert result["valid"] is False
    assert "sequence_length" in result["error"]


def test_allowed_properties_pass():
    cypher = """
    MATCH (g:Gene)
    WHERE g.cds_length > 500 AND g.exon_count > 5
    RETURN g as gene, [] as domains, g.species_taxon as species
    LIMIT 100
    """
    result = validate_cypher(cypher)
    assert result["valid"] is True
