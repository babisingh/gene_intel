"""
Tests for neighborhood_builder.py
"""

from app.ingestion.neighborhood_builder import build_neighborhood_edges


def test_builds_edges_for_nearby_genes(sample_gene_list):
    # GENE001 (end=2000) and GENE002 (start=3000): distance = 1000 < 10000 → should be linked
    edges = build_neighborhood_edges(sample_gene_list, window_bp=10000)
    from_to_pairs = {(e["from_id"], e["to_id"]) for e in edges}
    all_pairs = from_to_pairs | {(b, a) for a, b in from_to_pairs}
    assert ("GENE001", "GENE002") in all_pairs or ("GENE002", "GENE001") in all_pairs


def test_does_not_link_distant_genes(sample_gene_list):
    # GENE001 (end=2000) and GENE003 (start=20000): distance = 18000 > 10000 → not linked
    edges = build_neighborhood_edges(sample_gene_list, window_bp=10000)
    from_to_pairs = {(e["from_id"], e["to_id"]) for e in edges}
    all_pairs = from_to_pairs | {(b, a) for a, b in from_to_pairs}
    assert ("GENE001", "GENE003") not in all_pairs
    assert ("GENE003", "GENE001") not in all_pairs


def test_does_not_link_genes_on_different_chromosomes(sample_gene_list):
    # GENE001 (chr1) and GENE004 (chr2) should NOT be linked even if positions overlap
    edges = build_neighborhood_edges(sample_gene_list, window_bp=10000)
    from_to_pairs = {(e["from_id"], e["to_id"]) for e in edges}
    all_pairs = from_to_pairs | {(b, a) for a, b in from_to_pairs}
    assert ("GENE001", "GENE004") not in all_pairs


def test_deduplicates_pairs(sample_gene_list):
    edges = build_neighborhood_edges(sample_gene_list, window_bp=10000)
    pair_keys = [tuple(sorted([e["from_id"], e["to_id"]])) for e in edges]
    assert len(pair_keys) == len(set(pair_keys)), "Duplicate edges found"


def test_distance_is_non_negative(sample_gene_list):
    edges = build_neighborhood_edges(sample_gene_list, window_bp=10000)
    for edge in edges:
        assert edge["distance_bp"] >= 0


def test_empty_input_returns_no_edges():
    assert build_neighborhood_edges([]) == []


def test_single_gene_returns_no_edges():
    genes = [{"gene_id": "G1", "chromosome": "1", "start": 100, "end": 200}]
    assert build_neighborhood_edges(genes) == []
