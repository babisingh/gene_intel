"""
Tests for domain_ingest_ftp.py
"""

from __future__ import annotations

import gzip
import io
import os
import tempfile
from unittest.mock import MagicMock, patch
import pytest

from app.ingestion.domain_ingest_ftp import (
    stream_parse_protein2ipr,
    build_taxon_uniprot_map,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_gz_file(rows: list[list[str]]) -> str:
    """Write a gzip-compressed TSV file, return the path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".dat.gz", delete=False)
    with gzip.open(tmp.name, "wt", encoding="utf-8") as f:
        for cols in rows:
            f.write("\t".join(cols) + "\n")
    return tmp.name


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: stream parser filters correctly
# ─────────────────────────────────────────────────────────────────────────────

def test_stream_parser_filters_correctly():
    """Only rows for our species AND Pfam should be yielded."""
    our_accs = {"P31946", "P62258"}
    other_accs = {"A0A1B2", "Q9XYZ1"}

    rows = [
        # Our species, Pfam → INCLUDE
        ["P31946", "IPR000253", "14-3-3 protein", "PF00244", "14-3-3", "5", "247"],
        ["P62258", "IPR000253", "14-3-3 protein", "PF00244", "14-3-3", "5", "247"],
        # Other species → EXCLUDE
        ["A0A1B2", "IPR000253", "14-3-3 protein", "PF00244", "14-3-3", "5", "247"],
        ["Q9XYZ1", "IPR000111", "Other domain",   "PF00111", "Other",  "1", "100"],
        # Our species but NOT Pfam (SMART) → EXCLUDE
        ["P31946", "IPR000999", "SMART domain",   "SM00220", "Kinase", "10", "200"],
        # Our species, Pfam, different entry → INCLUDE
        ["P31946", "IPR000111", "Kinase",         "PF00069", "PK",     "10", "300"],
    ]

    gz_path = _make_gz_file(rows)
    try:
        filter_set = our_accs  # only our two proteins
        results = list(stream_parse_protein2ipr(gz_path, filter_set))
    finally:
        os.unlink(gz_path)

    # Should have 3 results: 2 PF00244 + 1 PF00069 for our species
    assert len(results) == 3

    for r in results:
        assert r["uniprot_acc"] in our_accs, f"Got unexpected acc: {r['uniprot_acc']}"
        assert r["pfam_acc"].startswith("PF"), f"Got non-Pfam acc: {r['pfam_acc']}"

    # Verify other species excluded
    for r in results:
        assert r["uniprot_acc"] not in other_accs


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: stream parser handles malformed lines
# ─────────────────────────────────────────────────────────────────────────────

def test_stream_parser_handles_malformed_lines():
    """Malformed lines (wrong column count) should be skipped, not raise exceptions."""
    our_accs = {"P31946"}
    rows = [
        # Malformed: too few columns
        ["P31946", "IPR000253"],
        # Malformed: only 4 cols
        ["P31946", "IPR000253", "name", "PF00244"],
        # Malformed: start is not a number
        ["P31946", "IPR000253", "14-3-3", "PF00244", "14-3-3", "abc", "247"],
        # Valid row
        ["P31946", "IPR000253", "14-3-3 protein", "PF00244", "14-3-3", "5", "247"],
    ]

    gz_path = _make_gz_file(rows)
    try:
        results = list(stream_parse_protein2ipr(gz_path, our_accs))
    finally:
        os.unlink(gz_path)

    # Should not raise, only the valid row yielded
    assert len(results) == 1
    assert results[0]["uniprot_acc"] == "P31946"


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: large file uses streaming (no list accumulation)
# ─────────────────────────────────────────────────────────────────────────────

def test_large_file_uses_streaming_not_memory():
    """
    Verify the parser uses streaming by checking it processes a large file
    without accumulating all results in memory at once.

    We test this indirectly by using a generator and consuming one item at a time.
    """
    our_accs = {"P00001"}
    rows = [
        ["P00001", "IPR000253", "Test protein", "PF00001", "Test", str(i), str(i + 100)]
        for i in range(1, 1001)  # 1000 rows
    ]

    gz_path = _make_gz_file(rows)
    try:
        gen = stream_parse_protein2ipr(gz_path, our_accs)

        # The result is a generator — we can consume one item at a time
        assert hasattr(gen, "__iter__"), "Expected generator"
        assert hasattr(gen, "__next__"), "Expected generator with __next__"

        # Consume first 10 items
        count = 0
        for item in gen:
            count += 1
            if count == 10:
                break

        # We consumed 10 items without loading everything into memory
        assert count == 10
    finally:
        os.unlink(gz_path)


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: build_taxon_uniprot_map
# ─────────────────────────────────────────────────────────────────────────────

def test_build_taxon_uniprot_map():
    """build_taxon_uniprot_map should return mapping from Neo4j results."""
    mock_session = MagicMock()
    mock_driver = MagicMock()
    mock_driver.session.return_value.__enter__ = lambda s, *a: mock_session
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    mock_records = [
        {"uniprot_acc": "P31946", "gene_id": "GENE001", "taxon_id": "9606"},
        {"uniprot_acc": "P62258", "gene_id": "GENE002", "taxon_id": "9606"},
    ]
    mock_session.run.return_value = iter(mock_records)

    mapping, acc_set = build_taxon_uniprot_map(mock_driver, [9606])

    assert "P31946" in mapping
    assert "P62258" in mapping
    assert mapping["P31946"]["gene_id"] == "GENE001"
    assert "P31946" in acc_set
    assert "P99999" not in acc_set  # not in our mock data
