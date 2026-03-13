"""
Tests for dialect_detector.py
"""

from app.ingestion.dialect_detector import detect_dialect


def test_detects_ensembl_gtf(sample_human_gtf):
    dialect = detect_dialect(sample_human_gtf)
    assert dialect == "ensembl_gtf"


def test_detects_ncbi_gff3(sample_ecoli_gff3):
    dialect = detect_dialect(sample_ecoli_gff3)
    assert dialect == "ncbi_gff3"
