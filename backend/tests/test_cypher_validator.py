"""
Tests for cypher_validator.py
"""

import pytest

from app.agents.cypher_validator import normalise_taxon_literals, validate_cypher


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


# ── Taxon IDs are strings in the graph ───────────────────────────────────────
# Gene.species_taxon and Species.taxon_id hold strings such as '9606', and an
# integer literal never equals them in Neo4j, so the validator quotes it.

# The query Claude wrote for "human genes with the longest coding sequence" on
# 2026-11-27 (Railway logs, 13:23 UTC), without the markdown fence around it.
REPRODUCTION_BEFORE = (
    "MATCH (g:Gene)\n"
    "WHERE g.species_taxon = 9606 AND g.biotype = 'protein_coding' AND g.cds_length IS NOT NULL\n"
    "RETURN g as gene, collect(DISTINCT null) as domains, g.species_taxon as species\n"
    "ORDER BY g.cds_length DESC\n"
    "LIMIT 300"
)
REPRODUCTION_AFTER = (
    "MATCH (g:Gene)\n"
    "WHERE g.species_taxon = '9606' AND g.biotype = 'protein_coding' AND g.cds_length IS NOT NULL\n"
    "RETURN g as gene, collect(DISTINCT null) as domains, g.species_taxon as species\n"
    "ORDER BY g.cds_length DESC\n"
    "LIMIT 300"
)


def test_reproduction_query_comes_back_with_a_quoted_taxon_id():
    result = validate_cypher(REPRODUCTION_BEFORE)
    assert result == {"valid": True, "error": None, "cypher": REPRODUCTION_AFTER}


def test_query_without_integer_taxon_ids_comes_back_unchanged():
    cypher = (
        "MATCH (g:Gene) WHERE g.species_taxon IN ['9606', '10090'] "
        "RETURN g as gene, [] as domains, g.species_taxon as species LIMIT 300"
    )
    assert validate_cypher(cypher) == {"valid": True, "error": None, "cypher": cypher}


@pytest.mark.parametrize("before, after", [
    ("WHERE g.species_taxon = 9606", "WHERE g.species_taxon = '9606'"),
    ("WHERE g.species_taxon=9606", "WHERE g.species_taxon='9606'"),
    ("WHERE g.species_taxon <> 9606", "WHERE g.species_taxon <> '9606'"),
    ("WHERE 9606 = g.species_taxon", "WHERE '9606' = g.species_taxon"),
    ("WHERE g.species_taxon IN [9606, 10090]", "WHERE g.species_taxon IN ['9606', '10090']"),
    ("WHERE g.species_taxon in [9606,'10090', 7955]",
     "WHERE g.species_taxon in ['9606','10090', '7955']"),
    ("WHERE g.species_taxon IN [\n  9606,\n  10090\n]",
     "WHERE g.species_taxon IN [\n  '9606',\n  '10090'\n]"),
    ("WHERE g1.species_taxon = 9606 AND g2.species_taxon = 7955",
     "WHERE g1.species_taxon = '9606' AND g2.species_taxon = '7955'"),
    ("WHERE s.taxon_id = 9606", "WHERE s.taxon_id = '9606'"),
    ("MATCH (s:Species {taxon_id: 9606})-[:HAS_GENE]->(g:Gene)",
     "MATCH (s:Species {taxon_id: '9606'})-[:HAS_GENE]->(g:Gene)"),
    ("MATCH (g:Gene {biotype: 'protein_coding', species_taxon: 9606})",
     "MATCH (g:Gene {biotype: 'protein_coding', species_taxon: '9606'})"),
])
def test_integer_taxon_ids_are_quoted(before, after):
    assert normalise_taxon_literals(before) == after


@pytest.mark.parametrize("cypher", [
    "WHERE g.species_taxon = '9606'",
    'WHERE g.species_taxon = "9606"',
    "WHERE g.species_taxon IN ['9606', '10090']",
    "WHERE toInteger(g.species_taxon) = 9606",              # compares numbers already
    "WHERE g.cds_length = 9606 AND g.exon_count IN [1, 2]",  # not taxon IDs
    "WHERE g.species_taxon_note = 9606",                     # a different property
    "WHERE g.name = 'g.species_taxon = 9606'",               # inside a string literal
    "WHERE g.species_taxon IN [toString(9606)]",             # a computed list
])
def test_other_literals_are_left_alone(cypher):
    assert normalise_taxon_literals(cypher) == cypher


def test_apostrophe_in_a_comment_does_not_hide_the_comparison():
    cypher = "// human's genes\nMATCH (g:Gene) WHERE g.species_taxon = 9606 RETURN g LIMIT 1"
    assert normalise_taxon_literals(cypher) == (
        "// human's genes\nMATCH (g:Gene) WHERE g.species_taxon = '9606' RETURN g LIMIT 1"
    )


def test_quoted_query_is_still_checked():
    result = validate_cypher("MATCH (g:Gene) WHERE g.species_taxon = 9606 DELETE g")
    assert result["valid"] is False
    assert "DELETE" in result["error"]
    assert result["cypher"] == "MATCH (g:Gene) WHERE g.species_taxon = '9606' DELETE g"
