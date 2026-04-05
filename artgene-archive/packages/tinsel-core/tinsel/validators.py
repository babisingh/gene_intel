"""Input validation helpers for biological sequences and gate scores."""

from __future__ import annotations

import re

VALID_AA = frozenset("ACDEFGHIKLMNPQRSTVWY")
VALID_NT = frozenset("ACGTU")


def is_valid_amino_acid_sequence(seq: str) -> bool:
    """Return True when *seq* contains only standard IUPAC amino-acid letters."""
    if not seq:
        return False
    return all(c.upper() in VALID_AA for c in seq)


def is_valid_nucleotide_sequence(seq: str) -> bool:
    """Return True when *seq* contains only A/C/G/T/U nucleotides."""
    if not seq:
        return False
    return all(c.upper() in VALID_NT for c in seq)


def validate_sequence_length(seq: str, min_len: int = 1, max_len: int = 10_000) -> bool:
    """Return True when sequence length is within [min_len, max_len]."""
    return min_len <= len(seq) <= max_len


def validate_plddt_score(score: float) -> bool:
    """Return True when pLDDT score is in [0, 100]."""
    return 0.0 <= score <= 100.0


def validate_probability(prob: float) -> bool:
    """Return True when a probability value is in [0, 1]."""
    return 0.0 <= prob <= 1.0


def validate_identity_percent(identity: float) -> bool:
    """Return True when sequence identity percentage is in [0, 100]."""
    return 0.0 <= identity <= 100.0


def sanitize_sequence_id(seq_id: str) -> str:
    """Replace characters that are unsafe in file names / identifiers."""
    return re.sub(r"[^a-zA-Z0-9_\-.]", "_", seq_id)
