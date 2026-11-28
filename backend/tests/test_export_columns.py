"""
graphdb/export_csv.py must list exactly the keys the loader writes for each
node. Its write_nodes() stops the graph image build on Railway when they
differ; this test finds the mismatch before a build does.
"""

import importlib.util
import os

import pytest

from app.ingestion.feature_extractor import extract_features
from app.ingestion.gtf_parser import parse_gtf_streaming

REPO = os.path.join(os.path.dirname(__file__), "..", "..")
EXPORT_CSV = os.path.join(REPO, "graphdb", "export_csv.py")
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def load_export_csv():
    spec = importlib.util.spec_from_file_location("export_csv", EXPORT_CSV)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The GFF3 file's transcripts and features for E. coli are built by the
# extractor, not read from transcript rows, so they are checked as well.
@pytest.mark.parametrize("fixture, dialect, taxon", [
    ("sample_isoforms.gtf", "ensembl_gtf", "9606"),
    ("sample_ecoli.gff3", "ncbi_gff3", "511145"),
])
def test_export_columns_match_the_extractor(fixture, dialect, taxon):
    columns = load_export_csv().NODE_COLUMNS
    genes, transcripts, features = extract_features(
        parse_gtf_streaming(os.path.join(FIXTURES, fixture), dialect), taxon)
    for kind, rows in (("genes", genes), ("transcripts", transcripts),
                       ("features", features)):
        names = {name for name, _ in columns[kind]}
        assert rows, kind
        for row in rows:
            assert set(row) == names, kind
