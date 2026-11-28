"""
graphdb/export_csv.py must list exactly the keys the loader writes for each
node. Its write_nodes() stops the graph image build on Railway when they
differ; this test finds the mismatch before a build does.
"""

import importlib.util
import os

from app.ingestion.feature_extractor import extract_features
from app.ingestion.gtf_parser import parse_gtf_streaming

REPO = os.path.join(os.path.dirname(__file__), "..", "..")
EXPORT_CSV = os.path.join(REPO, "graphdb", "export_csv.py")
FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_isoforms.gtf")


def load_export_csv():
    spec = importlib.util.spec_from_file_location("export_csv", EXPORT_CSV)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_export_columns_match_the_extractor():
    columns = load_export_csv().NODE_COLUMNS
    genes, transcripts, features = extract_features(
        parse_gtf_streaming(FIXTURE, "ensembl_gtf"), "9606")
    for kind, rows in (("genes", genes), ("transcripts", transcripts),
                       ("features", features)):
        names = {name for name, _ in columns[kind]}
        assert rows, kind
        for row in rows:
            assert set(row) == names, kind
