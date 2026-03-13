"""
Shared test fixtures for Gene-Intel backend tests.
"""

import os
import pytest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def sample_human_gtf():
    return os.path.join(FIXTURES_DIR, "sample_human.gtf")


@pytest.fixture
def sample_ecoli_gff3():
    return os.path.join(FIXTURES_DIR, "sample_ecoli.gff3")


@pytest.fixture
def sample_biomart_tsv():
    return os.path.join(FIXTURES_DIR, "sample_biomart.tsv")


@pytest.fixture
def sample_gene_list():
    """Minimal gene list for neighborhood tests."""
    return [
        {"gene_id": "GENE001", "chromosome": "1", "start": 1000, "end": 2000},
        {"gene_id": "GENE002", "chromosome": "1", "start": 3000, "end": 4000},
        {"gene_id": "GENE003", "chromosome": "1", "start": 20000, "end": 21000},
        {"gene_id": "GENE004", "chromosome": "2", "start": 1000, "end": 2000},
        {"gene_id": "GENE005", "chromosome": "1", "start": 5000, "end": 6000},
    ]
