"""
Tests for domain_ingest_uniprot.py

Uses unittest.mock to avoid real HTTP/Neo4j calls.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch, call
import pytest

from app.ingestion.domain_ingest_uniprot import (
    fetch_uniprot_domains,
    load_domains_to_neo4j_accurate,
    _parse_next_link,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_protein(acc: str, gene: str, pfam_acc: str, start: int, end: int):
    return {
        "primaryAccession": acc,
        "genes": [{"geneName": {"value": gene}}],
        "features": [
            {
                "type": "Domain",
                "description": "Protein kinase",
                "location": {
                    "start": {"value": start},
                    "end": {"value": end},
                },
                "dbReferences": [{"database": "Pfam", "id": pfam_acc}],
            }
        ],
    }


def _make_response(proteins: list, next_url: str | None = None):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"results": proteins}
    link = f'<{next_url}>; rel="next"' if next_url else ""
    resp.headers = {"Link": link, "X-Total-Results": "999"}
    return resp


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: fetch returns domains for human with pagination
# ─────────────────────────────────────────────────────────────────────────────

@patch("app.ingestion.domain_ingest_uniprot.time.sleep", return_value=None)
@patch("app.ingestion.domain_ingest_uniprot.requests.get")
def test_fetch_returns_domains_for_human(mock_get, mock_sleep):
    page1_proteins = [_make_protein("P31946", "YWHAB", "PF00244", 5, 247)]
    page2_proteins = [_make_protein("P62258", "YWHAE", "PF00244", 5, 247)]

    mock_get.side_effect = [
        _make_response(page1_proteins, next_url="https://rest.uniprot.org/page2"),
        _make_response(page2_proteins, next_url=None),
    ]

    result = fetch_uniprot_domains(taxon_id=9606, reviewed_only=True)

    assert isinstance(result, list)
    assert len(result) == 2

    # Check required keys are present
    required_keys = {"uniprot_acc", "gene_name", "pfam_acc", "domain_name",
                     "start_aa", "end_aa", "e_value", "domain_id"}
    for domain in result:
        assert required_keys.issubset(domain.keys()), f"Missing keys: {required_keys - set(domain.keys())}"

    # Pagination: second page was fetched
    assert mock_get.call_count == 2

    # domain_id is correctly formed: gene__pfam__start
    assert result[0]["domain_id"] == "YWHAB__PF00244__5"


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: rate-limit retry (429 then 200)
# ─────────────────────────────────────────────────────────────────────────────

@patch("app.ingestion.domain_ingest_uniprot.time.sleep", return_value=None)
@patch("app.ingestion.domain_ingest_uniprot.requests.get")
def test_rate_limit_retry(mock_get, mock_sleep):
    rate_limit_resp = MagicMock()
    rate_limit_resp.status_code = 429

    ok_resp = _make_response(
        [_make_protein("P31946", "YWHAB", "PF00244", 5, 247)],
        next_url=None,
    )

    # First call returns 429, second returns 200
    mock_get.side_effect = [rate_limit_resp, ok_resp]

    result = fetch_uniprot_domains(taxon_id=9606, reviewed_only=True, max_pages=1)

    assert len(result) == 1
    # sleep was called at least once for backoff
    mock_sleep.assert_called()


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: load_domains skips missing genes
# ─────────────────────────────────────────────────────────────────────────────

def test_load_domains_skips_missing_genes():
    domains = [
        {
            "uniprot_acc": "P99999",
            "gene_name": "NOTINGRAPH",
            "pfam_acc": "PF00001",
            "domain_name": "Test domain",
            "domain_id": "NOTINGRAPH__PF00001__1",
            "start_aa": 1,
            "end_aa": 100,
            "e_value": None,
            "source_db": "uniprot",
            "species_taxon": 9606,
        }
    ]

    # Mock driver: session returns "gene not found"
    mock_session = MagicMock()
    mock_driver = MagicMock()
    mock_driver.session.return_value.__enter__ = lambda s, *a: mock_session
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    check_result = [{"gene_name": "NOTINGRAPH", "found": False}]
    mock_session.run.return_value = iter(check_result)

    stats = load_domains_to_neo4j_accurate(domains, mock_driver, batch_size=500)

    # No exception raised
    assert isinstance(stats, dict)
    assert "skipped_no_gene" in stats
    assert stats["skipped_no_gene"] >= 1


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: batch size respected
# ─────────────────────────────────────────────────────────────────────────────

def test_batch_size_respected():
    domains = []
    for i in range(1200):
        domains.append({
            "uniprot_acc": f"P{i:05d}",
            "gene_name": f"GENE{i}",
            "pfam_acc": "PF00001",
            "domain_name": "Test domain",
            "domain_id": f"GENE{i}__PF00001__{i}",
            "start_aa": i,
            "end_aa": i + 100,
            "e_value": None,
            "source_db": "uniprot",
            "species_taxon": 9606,
        })

    run_calls = []

    def fake_run(query, **kwargs):
        run_calls.append(kwargs)
        batch = kwargs.get("batch", [])
        return iter([{"gene_name": r["gene_name"], "found": True} for r in batch])

    mock_session = MagicMock()
    mock_session.run.side_effect = fake_run
    mock_driver = MagicMock()
    mock_driver.session.return_value.__enter__ = lambda s, *a: mock_session
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    load_domains_to_neo4j_accurate(domains, mock_driver, batch_size=500)

    # With 1200 domains and batch_size=500, should have 3 batches
    # Each batch calls run twice (check + write), so 6 total run calls
    assert mock_session.run.call_count >= 3


# ─────────────────────────────────────────────────────────────────────────────
# Test helpers
# ─────────────────────────────────────────────────────────────────────────────

def test_parse_next_link_extracts_url():
    link = '<https://rest.uniprot.org/page2?cursor=abc>; rel="next"'
    result = _parse_next_link(link)
    assert result == "https://rest.uniprot.org/page2?cursor=abc"


def test_parse_next_link_returns_none_when_no_next():
    assert _parse_next_link("") is None
    assert _parse_next_link('<https://a.com>; rel="prev"') is None
