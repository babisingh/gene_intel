"""Unit tests for tinsel.validators — 13 tests."""

import pytest

from tinsel.validators import (
    is_valid_amino_acid_sequence,
    is_valid_nucleotide_sequence,
    sanitize_sequence_id,
    validate_identity_percent,
    validate_plddt_score,
    validate_probability,
    validate_sequence_length,
)


def test_valid_amino_acid_sequence():
    assert is_valid_amino_acid_sequence("MKTLLLTLVVVTIVCLDLGAVS") is True


def test_invalid_amino_acid_sequence_contains_digit():
    assert is_valid_amino_acid_sequence("MKT1LL") is False


def test_empty_amino_acid_sequence_is_invalid():
    assert is_valid_amino_acid_sequence("") is False


def test_valid_nucleotide_sequence_dna():
    assert is_valid_nucleotide_sequence("ATCGATCG") is True


def test_valid_nucleotide_sequence_rna():
    assert is_valid_nucleotide_sequence("AUCGAUCG") is True


def test_invalid_nucleotide_sequence():
    assert is_valid_nucleotide_sequence("ATCGX") is False


def test_empty_nucleotide_sequence_is_invalid():
    assert is_valid_nucleotide_sequence("") is False


def test_validate_sequence_length_within_bounds():
    assert validate_sequence_length("ACGT", min_len=2, max_len=10) is True


def test_validate_sequence_length_too_short():
    assert validate_sequence_length("A", min_len=2, max_len=10) is False


def test_validate_plddt_score_valid():
    assert validate_plddt_score(85.5) is True
    assert validate_plddt_score(0.0) is True
    assert validate_plddt_score(100.0) is True


def test_validate_plddt_score_out_of_range():
    assert validate_plddt_score(-1.0) is False
    assert validate_plddt_score(101.0) is False


def test_validate_probability():
    assert validate_probability(0.0) is True
    assert validate_probability(1.0) is True
    assert validate_probability(0.5) is True
    assert validate_probability(-0.01) is False
    assert validate_probability(1.01) is False


def test_validate_identity_percent():
    assert validate_identity_percent(0.0) is True
    assert validate_identity_percent(99.9) is True
    assert validate_identity_percent(100.0) is True
    assert validate_identity_percent(-0.1) is False
    assert validate_identity_percent(100.1) is False


def test_sanitize_sequence_id_clean():
    assert sanitize_sequence_id("seq_001.A") == "seq_001.A"


def test_sanitize_sequence_id_replaces_spaces_and_special():
    result = sanitize_sequence_id("seq 001/A@B")
    assert " " not in result
    assert "/" not in result
    assert "@" not in result
