"""Utility functions for sequence analysis in the Tinsel pipeline."""

from __future__ import annotations

from typing import List

_CODON_TABLE: dict[str, str] = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
    "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
    "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
    "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}

_AA_WEIGHTS: dict[str, float] = {
    "A": 89.1,  "R": 174.2, "N": 132.1, "D": 133.1, "C": 121.2,
    "E": 147.1, "Q": 146.2, "G": 75.0,  "H": 155.2, "I": 131.2,
    "L": 131.2, "K": 146.2, "M": 149.2, "F": 165.2, "P": 115.1,
    "S": 105.1, "T": 119.1, "W": 204.2, "Y": 181.2, "V": 117.1,
}


def compute_gc_content(sequence: str) -> float:
    """Return GC fraction (0–1) for a nucleotide sequence."""
    if not sequence:
        return 0.0
    upper = sequence.upper()
    gc = upper.count("G") + upper.count("C")
    return gc / len(upper)


def translate_nucleotide(sequence: str) -> str:
    """Translate a nucleotide sequence to a protein string (stops at first '*')."""
    upper = sequence.upper().replace("U", "T")
    protein: list[str] = []
    for i in range(0, len(upper) - 2, 3):
        codon = upper[i : i + 3]
        aa = _CODON_TABLE.get(codon, "X")
        if aa == "*":
            break
        protein.append(aa)
    return "".join(protein)


def chunk_sequence(sequence: str, chunk_size: int) -> List[str]:
    """Split *sequence* into non-overlapping chunks of *chunk_size*."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer")
    return [sequence[i : i + chunk_size] for i in range(0, len(sequence), chunk_size)]


def compute_molecular_weight(sequence: str) -> float:
    """Return approximate monoisotopic MW (Da) for an amino-acid sequence."""
    if not sequence:
        return 0.0
    total = sum(_AA_WEIGHTS.get(aa.upper(), 110.0) for aa in sequence)
    # Subtract one water molecule per peptide bond
    total -= (len(sequence) - 1) * 18.0
    return round(total, 2)
