"""
Tests for agent_a_semantic.py

Note: These tests mock the Claude API to avoid API calls in CI.
Integration tests (marked with @pytest.mark.integration) require a real API key.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.agents.agent_a_semantic import generate_cypher, build_system_prompt, strip_code_fence
from app.agents.bio_dictionary import BIO_DICTIONARY, LOADED_SPECIES


def test_system_prompt_contains_bio_dictionary_concepts():
    prompt = build_system_prompt()
    for concept in list(BIO_DICTIONARY.keys())[:5]:  # Spot-check first 5 concepts
        assert concept in prompt


def test_system_prompt_contains_gene_properties():
    prompt = build_system_prompt()
    assert "cds_length" in prompt
    assert "species_taxon" in prompt
    assert "exon_count" in prompt


def test_system_prompt_states_property_types():
    prompt = build_system_prompt()
    assert "species_taxon (string)" in prompt
    assert "chromosome (string)" in prompt
    assert "cds_length (integer)" in prompt
    assert "utr_cds_ratio (float)" in prompt


def test_system_prompt_lists_every_loaded_species_with_a_quoted_taxon_id():
    prompt = build_system_prompt()
    assert len(LOADED_SPECIES) == 15
    for taxon_id, (common_name, scientific_name) in LOADED_SPECIES.items():
        assert f"- '{taxon_id}': {common_name} ({scientific_name})" in prompt


def test_system_prompt_filter_examples_quote_taxon_ids():
    prompt = build_system_prompt()
    assert "g.species_taxon = '9606'" in prompt
    assert "g.species_taxon IN ['9606', '10090']" in prompt
    assert "[list_of_taxon_ids]" not in prompt


def _make_mock_response(cypher_text: str):
    mock_content = MagicMock()
    mock_content.text = cypher_text
    mock_response = MagicMock()
    mock_response.content = [mock_content]
    return mock_response


def test_generate_cypher_returns_success_for_valid_cypher():
    valid_cypher = (
        "MATCH (g:Gene) WHERE g.biotype = 'protein_coding' "
        "RETURN g as gene, collect(DISTINCT d.domain_id) as domains, "
        "g.species_taxon as species LIMIT 300"
    )
    with patch("app.agents.agent_a_semantic.client") as mock_client:
        mock_client.messages.create.return_value = _make_mock_response(valid_cypher)
        result = generate_cypher("Find all protein coding genes")

    assert result["success"] is True
    assert result["cypher"] == valid_cypher
    assert result["error"] is None


def test_generate_cypher_returns_failure_for_invalid_cypher():
    invalid_cypher = "MATCH (g:Gene) DELETE g"
    with patch("app.agents.agent_a_semantic.client") as mock_client:
        mock_client.messages.create.return_value = _make_mock_response(invalid_cypher)
        result = generate_cypher("Delete all genes")

    assert result["success"] is False
    assert result["error"] is not None


def test_generate_cypher_strips_whitespace():
    cypher_with_whitespace = (
        "\n\n  MATCH (g:Gene) RETURN g as gene, [] as domains, "
        "g.species_taxon as species LIMIT 10  \n"
    )
    with patch("app.agents.agent_a_semantic.client") as mock_client:
        mock_client.messages.create.return_value = _make_mock_response(cypher_with_whitespace)
        result = generate_cypher("test query")

    # The cypher should be stripped
    assert not result["cypher"].startswith("\n")
    assert not result["cypher"].endswith("\n")


def test_generate_cypher_returns_the_query_with_taxon_ids_quoted():
    claude_cypher = (
        "MATCH (g:Gene) WHERE g.species_taxon = 9606 "
        "RETURN g as gene, [] as domains, g.species_taxon as species LIMIT 300"
    )
    with patch("app.agents.agent_a_semantic.client") as mock_client:
        mock_client.messages.create.return_value = _make_mock_response(claude_cypher)
        result = generate_cypher("human genes")

    assert result == {
        "cypher": (
            "MATCH (g:Gene) WHERE g.species_taxon = '9606' "
            "RETURN g as gene, [] as domains, g.species_taxon as species LIMIT 300"
        ),
        "success": True,
        "error": None,
    }


# ── Markdown code fences ─────────────────────────────────────────────────────

BARE = "MATCH (g:Gene) RETURN g as gene, [] as domains, g.species_taxon as species LIMIT 10"


@pytest.mark.parametrize("reply", [
    f"```cypher\n{BARE}\n```",
    f"```Cypher\n{BARE}\n```",
    f"```\n{BARE}\n```",
    f"```{BARE}```",
    f"Here is the query:\n```cypher\n{BARE}\n```\nIt lists genes.",
    BARE,
])
def test_strip_code_fence_returns_the_bare_query(reply):
    assert strip_code_fence(reply) == BARE


# The reply Claude gave for "human genes with the longest coding sequence" on
# 2026-11-27. Neo4j rejected it with a SyntaxError at line 1, column 1 because
# of the fence (Railway logs, 13:23 UTC), and the search reported 0 results.
CLAUDE_REPLY_2026_11_27 = (
    "```cypher\n"
    "MATCH (g:Gene)\n"
    "WHERE g.species_taxon = 9606 AND g.biotype = 'protein_coding' AND g.cds_length IS NOT NULL\n"
    "RETURN g as gene, collect(DISTINCT null) as domains, g.species_taxon as species\n"
    "ORDER BY g.cds_length DESC\n"
    "LIMIT 300\n"
    "```"
)


def test_generate_cypher_fixes_the_reply_from_the_reproduction():
    with patch("app.agents.agent_a_semantic.client") as mock_client:
        mock_client.messages.create.return_value = _make_mock_response(CLAUDE_REPLY_2026_11_27)
        result = generate_cypher("human genes with the longest coding sequence")

    assert result == {
        "cypher": (
            "MATCH (g:Gene)\n"
            "WHERE g.species_taxon = '9606' AND g.biotype = 'protein_coding' AND g.cds_length IS NOT NULL\n"
            "RETURN g as gene, collect(DISTINCT null) as domains, g.species_taxon as species\n"
            "ORDER BY g.cds_length DESC\n"
            "LIMIT 300"
        ),
        "success": True,
        "error": None,
    }
