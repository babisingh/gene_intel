"""
Tests for domain_ingest_interpro.py
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch, call
import pytest

from app.ingestion.domain_ingest_interpro import (
    fetch_interpro_domains_for_taxon,
    enrich_existing_domains,
    _parse_domain_from_result,
    _RATE_LIMIT_DELAY,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_interpro_result(protein_acc: str, pfam_acc: str, start: int, end: int, score=1e-10):
    return {
        "metadata": {"accession": protein_acc},
        "entries": [
            {
                "metadata": {
                    "accession": pfam_acc,
                    "name": {"name": "Protein kinase"},
                },
                "protein_structure_mapping": {
                    protein_acc: [
                        {"start": start, "end": end, "score": score}
                    ]
                },
            }
        ],
    }


def _make_interpro_page(results: list, next_url: str | None = None):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"results": results, "next": next_url}
    return resp


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: rate limit enforced
# ─────────────────────────────────────────────────────────────────────────────

@patch("app.ingestion.domain_ingest_interpro.requests.get")
@patch("app.ingestion.domain_ingest_interpro.time.sleep")
def test_rate_limit_enforced(mock_sleep, mock_get):
    """Verify sleep is called before each request with at least RATE_LIMIT_DELAY."""
    page1 = _make_interpro_page(
        [_make_interpro_result("P11111", "PF00069", 10, 200)],
        next_url="https://www.ebi.ac.uk/interpro/api/page2",
    )
    page2 = _make_interpro_page(
        [_make_interpro_result("P22222", "PF00244", 5, 247)],
        next_url=None,
    )
    mock_get.side_effect = [page1, page2]

    fetch_interpro_domains_for_taxon(taxon_id=9606, page_size=200)

    # sleep should be called once per request (2 pages = 2 sleeps)
    assert mock_sleep.call_count >= 2
    # Each sleep call should be at least RATE_LIMIT_DELAY
    for c in mock_sleep.call_args_list:
        delay = c.args[0] if c.args else c.kwargs.get("secs", 0)
        assert delay >= _RATE_LIMIT_DELAY, f"Sleep delay {delay} < {_RATE_LIMIT_DELAY}"


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: pagination exhausted (3 pages, last has next=null)
# ─────────────────────────────────────────────────────────────────────────────

@patch("app.ingestion.domain_ingest_interpro.requests.get")
@patch("app.ingestion.domain_ingest_interpro.time.sleep", return_value=None)
def test_pagination_exhausted(mock_sleep, mock_get):
    page1 = _make_interpro_page(
        [_make_interpro_result("P11111", "PF00069", 10, 200)],
        next_url="https://api/page2",
    )
    page2 = _make_interpro_page(
        [_make_interpro_result("P22222", "PF00244", 5, 247)],
        next_url="https://api/page3",
    )
    page3 = _make_interpro_page(
        [_make_interpro_result("P33333", "PF00400", 1, 150)],
        next_url=None,  # last page
    )
    mock_get.side_effect = [page1, page2, page3]

    result = fetch_interpro_domains_for_taxon(taxon_id=9606, page_size=1)

    assert mock_get.call_count == 3
    assert len(result) == 3


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: enrich only updates NULL e-values
# ─────────────────────────────────────────────────────────────────────────────

@patch("app.ingestion.domain_ingest_interpro.fetch_interpro_domains_for_taxon")
def test_enrich_only_updates_null_evalues(mock_fetch):
    mock_fetch.return_value = [
        {
            "uniprot_acc": "P11111",
            "pfam_acc": "PF00069",
            "start_aa": 10,
            "end_aa": 200,
            "e_value": 1e-15,
            "source_db": "pfam_interpro",
        }
    ]

    # Mock Neo4j session
    mock_session = MagicMock()
    mock_driver = MagicMock()
    mock_driver.session.return_value.__enter__ = lambda s, *a: mock_session
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    mock_result = MagicMock()
    mock_summary = MagicMock()
    mock_summary.counters.properties_set = 1
    mock_result.consume.return_value = mock_summary
    mock_session.run.return_value = mock_result

    stats = enrich_existing_domains(taxon_id=9606, driver=mock_driver)

    assert isinstance(stats, dict)
    assert "enriched" in stats
    # Verify the WHERE clause in the Cypher contains IS NULL check
    called_query = mock_session.run.call_args_list[0].args[0]
    assert "IS NULL" in called_query


# ─────────────────────────────────────────────────────────────────────────────
# Test: _parse_domain_from_result handles KeyError gracefully
# ─────────────────────────────────────────────────────────────────────────────

def test_parse_domain_handles_malformed():
    malformed = {"metadata": {}, "entries": [{"bad_key": "value"}]}
    result = _parse_domain_from_result(malformed)
    assert result == []  # no exception, empty list


def test_parse_domain_skips_non_pfam():
    result_with_smart = {
        "metadata": {"accession": "P11111"},
        "entries": [
            {
                "metadata": {"accession": "SM00220", "name": {"name": "SMART domain"}},
                "protein_structure_mapping": {
                    "P11111": [{"start": 1, "end": 100, "score": 1e-5}]
                },
            }
        ],
    }
    domains = _parse_domain_from_result(result_with_smart)
    # SMART accessions start with SM, not PF — should be skipped
    assert all(d["pfam_acc"].startswith("PF") for d in domains)
    assert len(domains) == 0
