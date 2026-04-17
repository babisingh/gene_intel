"""Unit tests for tinsel.utils — 13 tests."""

import pytest

from tinsel.utils import (
    chunk_sequence,
    compute_gc_content,
    compute_molecular_weight,
    translate_nucleotide,
)


# ---------------------------------------------------------------------------
# compute_gc_content
# ---------------------------------------------------------------------------

def test_gc_content_all_gc():
    assert compute_gc_content("GCGCGC") == pytest.approx(1.0)


def test_gc_content_no_gc():
    assert compute_gc_content("ATATAT") == pytest.approx(0.0)


def test_gc_content_mixed():
    # ATGC → 2 GC out of 4
    assert compute_gc_content("ATGC") == pytest.approx(0.5)


def test_gc_content_empty_sequence():
    assert compute_gc_content("") == pytest.approx(0.0)


def test_gc_content_case_insensitive():
    assert compute_gc_content("atgc") == pytest.approx(compute_gc_content("ATGC"))


# ---------------------------------------------------------------------------
# translate_nucleotide
# ---------------------------------------------------------------------------

def test_translate_start_codon():
    # ATG → M
    assert translate_nucleotide("ATG") == "M"


def test_translate_simple_peptide():
    # ATG TTT → M F
    assert translate_nucleotide("ATGTTT") == "MF"


def test_translate_stops_at_stop_codon():
    # ATG TAA TTT — stop at TAA, so only "M"
    assert translate_nucleotide("ATGTAATTT") == "M"


def test_translate_rna_input():
    # RNA: AUG → ATG internally
    assert translate_nucleotide("AUG") == "M"


# ---------------------------------------------------------------------------
# chunk_sequence
# ---------------------------------------------------------------------------

def test_chunk_sequence_even_split():
    assert chunk_sequence("ATCGATCG", 4) == ["ATCG", "ATCG"]


def test_chunk_sequence_uneven_split():
    chunks = chunk_sequence("ATCGA", 3)
    assert chunks == ["ATC", "GA"]


def test_chunk_sequence_single_chunk():
    assert chunk_sequence("ATCG", 10) == ["ATCG"]


def test_chunk_sequence_invalid_size():
    with pytest.raises(ValueError):
        chunk_sequence("ATCG", 0)


# ---------------------------------------------------------------------------
# compute_molecular_weight
# ---------------------------------------------------------------------------

def test_molecular_weight_single_aa():
    # Single amino acid: no peptide bond subtraction
    mw = compute_molecular_weight("M")
    assert mw == pytest.approx(149.2, abs=0.1)


def test_molecular_weight_empty_sequence():
    assert compute_molecular_weight("") == pytest.approx(0.0)


def test_molecular_weight_increases_with_length():
    mw2 = compute_molecular_weight("MA")
    mw1 = compute_molecular_weight("M")
    assert mw2 > mw1
