"""
Tests for the domain ingestion orchestrator (run_ingest.py extensions).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call
import pytest

from app.ingestion.run_ingest import (
    _auto_select_domain_route,
    run_domain_ingest,
    print_coverage_report,
    _WELL_ANNOTATED,
    _LOW_COVERAGE,
)


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: route selection for model organisms
# (patch in the modules where functions are imported inside run_domain_ingest)
# ─────────────────────────────────────────────────────────────────────────────

@patch("app.ingestion.domain_ingest_interpro.enrich_existing_domains")
@patch("app.ingestion.domain_ingest_uniprot.run_uniprot_domain_ingest")
def test_route_selection_model_organism(mock_uniprot, mock_interpro):
    """Human (9606) should use UniProt then InterPro enrichment. No InterProScan."""
    mock_driver = MagicMock()
    mock_uniprot.return_value = {"loaded": 100, "skipped_no_gene": 0, "errors": 0}
    mock_interpro.return_value = {"enriched": 50, "not_found": 10}

    with patch("app.ingestion.domain_ingest_uniprot.run_uniprot_domain_ingest",
               return_value={"loaded": 100, "skipped_no_gene": 0, "errors": 0}), \
         patch("app.ingestion.domain_ingest_interpro.enrich_existing_domains",
               return_value={"enriched": 50, "not_found": 10}) as mock_enrich:
        run_domain_ingest("9606", mock_driver, domain_source="both", skip_enrichment=False)
        # InterPro enrichment should have been called
        mock_enrich.assert_called_once_with(9606, mock_driver)


@patch("app.ingestion.domain_ingest_interproscan.run_interproscan_ingest")
def test_interproscan_not_called_for_model_organism(mock_iprs):
    """InterProScan should NOT be called for well-annotated model organisms."""
    mock_driver = MagicMock()

    with patch("app.ingestion.domain_ingest_uniprot.run_uniprot_domain_ingest",
               return_value={"loaded": 100, "skipped_no_gene": 0, "errors": 0}), \
         patch("app.ingestion.domain_ingest_interpro.enrich_existing_domains",
               return_value={"enriched": 50, "not_found": 10}):
        run_domain_ingest("9606", mock_driver, domain_source="both")

    mock_iprs.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: route selection for exotic species
# ─────────────────────────────────────────────────────────────────────────────

def test_auto_select_model_organism():
    """Well-annotated species should get 'both' route."""
    for taxon_id in _WELL_ANNOTATED:
        result = _auto_select_domain_route(taxon_id)
        assert result == "both", f"Expected 'both' for taxon {taxon_id}, got '{result}'"


def test_auto_select_low_coverage():
    """Low-coverage species should get 'both_unreviewed' route."""
    for taxon_id in _LOW_COVERAGE:
        result = _auto_select_domain_route(taxon_id)
        assert result == "both_unreviewed", \
            f"Expected 'both_unreviewed' for taxon {taxon_id}, got '{result}'"


def test_route_selection_exotic_species_with_fasta():
    """Octopus (175781) with genome FASTA should trigger InterProScan."""
    mock_driver = MagicMock()

    with patch("app.ingestion.domain_ingest_uniprot.run_uniprot_domain_ingest",
               return_value={"loaded": 100, "skipped_no_gene": 0, "errors": 0}), \
         patch("app.ingestion.domain_ingest_interpro.enrich_existing_domains",
               return_value={"enriched": 10, "not_found": 90}), \
         patch("app.ingestion.domain_ingest_interproscan.run_interproscan_ingest",
               return_value={"loaded": 200, "skipped": False}) as mock_iprs, \
         patch("os.path.exists", return_value=True):
        run_domain_ingest("175781", mock_driver, domain_source="both_unreviewed")
        # InterProScan is called because 175781 is in _LOW_COVERAGE
        mock_iprs.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: coverage report warns on low coverage
# ─────────────────────────────────────────────────────────────────────────────

def test_coverage_report_warns_low_coverage(capsys):
    """Species with <30% domain coverage should show WARN or ALERT."""
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = lambda s, *a: mock_session
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    # Mock: one species with 10% coverage (ALERT threshold)
    mock_session.run.side_effect = [
        iter([{
            "species": "King cobra",
            "taxon": "8665",
            "total_genes": 1000,
            "genes_with_domains": 100,  # 10% coverage
        }]),
        iter([]),  # top domain query
    ]

    print_coverage_report(mock_driver)
    captured = capsys.readouterr()

    # Should show ALERT for 10% coverage
    assert "ALERT" in captured.out or "WARN" in captured.out or "⚠" in captured.out or "!" in captured.out


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: skip_enrichment flag prevents InterPro call
# ─────────────────────────────────────────────────────────────────────────────

def test_skip_enrichment_flag():
    """--skip-domain-enrichment should prevent InterPro enrichment call."""
    mock_driver = MagicMock()

    with patch("app.ingestion.domain_ingest_uniprot.run_uniprot_domain_ingest",
               return_value={"loaded": 100, "skipped_no_gene": 0, "errors": 0}), \
         patch("app.ingestion.domain_ingest_interpro.enrich_existing_domains",
               return_value={"enriched": 50, "not_found": 10}) as mock_enrich:
        run_domain_ingest(
            "9606", mock_driver,
            domain_source="both",
            skip_enrichment=True,
        )
        mock_enrich.assert_not_called()
