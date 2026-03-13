"""
Tests for agent_a_semantic.py

Note: These tests mock the Claude API to avoid API calls in CI.
Integration tests (marked with @pytest.mark.integration) require a real API key.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.agents.agent_a_semantic import generate_cypher, build_system_prompt
from app.agents.bio_dictionary import BIO_DICTIONARY


def test_system_prompt_contains_bio_dictionary_concepts():
    prompt = build_system_prompt()
    for concept in list(BIO_DICTIONARY.keys())[:5]:  # Spot-check first 5 concepts
        assert concept in prompt


def test_system_prompt_contains_gene_properties():
    prompt = build_system_prompt()
    assert "cds_length" in prompt
    assert "species_taxon" in prompt
    assert "exon_count" in prompt


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
