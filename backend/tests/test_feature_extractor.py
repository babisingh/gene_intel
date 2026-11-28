"""
Tests for feature_extractor.py: a gene's CDS length, exon count and UTR
values come from one transcript, its canonical transcript, and not from a
sum over all of its transcripts.

fixtures/sample_isoforms.gtf has one gene per case.
"""

import os

import pytest

from app.ingestion.feature_extractor import extract_features
from app.ingestion.gtf_parser import parse_gtf_streaming

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_isoforms.gtf")


@pytest.fixture(scope="module")
def extracted():
    genes, transcripts, features = extract_features(
        parse_gtf_streaming(FIXTURE, "ensembl_gtf"), "9606")
    return ({g["gene_id"]: g for g in genes},
            {t["transcript_id"]: t for t in transcripts},
            features)


def test_the_tagged_canonical_transcript_wins_over_a_longer_cds(extracted):
    genes, transcripts, _ = extracted
    gene = genes["GENE1"]
    assert gene["canonical_transcript_id"] == "TX1A"
    assert gene["canonical_source"] == "Ensembl_canonical"
    # TX1A alone: CDS 150-199 and 300-349, exons 100-199 and 300-399
    assert gene["cds_length"] == 100
    assert gene["exon_count"] == 2
    assert gene["utr5_length"] == 50
    assert gene["utr3_length"] == 50
    assert gene["utr_cds_ratio"] == 1.0
    # The other transcript keeps its own values
    assert transcripts["TX1B"]["cds_length"] == 250
    assert transcripts["TX1B"]["exon_count"] == 3


def test_gene_values_are_not_sums_over_its_transcripts(extracted):
    genes, transcripts, _ = extracted
    own = [t for t in transcripts.values() if t["gene_id"] == "GENE1"]
    assert genes["GENE1"]["cds_length"] < sum(t["cds_length"] for t in own)
    assert genes["GENE1"]["exon_count"] < sum(t["exon_count"] for t in own)


def test_without_a_tag_the_longest_cds_wins_then_the_longest_transcript(extracted):
    genes, _, _ = extracted
    gene = genes["GENE2"]
    # TX2A and TX2B both have 90 bp of CDS; TX2B has 200 bp of exons, TX2A
    # 100. TX2C has 500 bp of exons but no CDS.
    assert gene["canonical_transcript_id"] == "TX2B"
    assert gene["canonical_source"] == "longest_cds"
    assert gene["cds_length"] == 90
    assert gene["exon_count"] == 2
    assert gene["utr_cds_ratio"] == 0.0


def test_a_noncoding_gene_takes_its_longest_transcript(extracted):
    genes, _, _ = extracted
    gene = genes["GENE3"]
    assert gene["canonical_transcript_id"] == "TX3B"
    assert gene["canonical_source"] == "longest_transcript"
    assert gene["cds_length"] == 0
    assert gene["exon_count"] == 1
    assert gene["utr_cds_ratio"] is None


def test_a_tie_goes_to_the_smaller_transcript_id(extracted):
    genes, _, _ = extracted
    assert genes["GENE4"]["canonical_transcript_id"] == "TX4A"


def test_a_gene_without_transcripts_keeps_empty_values(extracted):
    genes, _, _ = extracted
    gene = genes["GENE5"]
    assert gene["cds_length"] == 0
    assert gene["exon_count"] == 0
    assert gene["utr_cds_ratio"] is None
    assert gene["canonical_transcript_id"] is None
    assert gene["canonical_source"] is None


def test_each_gene_has_one_canonical_transcript_and_names_it(extracted):
    genes, transcripts, _ = extracted
    canonical = {}
    for t in transcripts.values():
        canonical.setdefault(t["gene_id"], [])
        if t["is_canonical"]:
            canonical[t["gene_id"]].append(t["transcript_id"])
    assert set(canonical) == {"GENE1", "GENE2", "GENE3", "GENE4"}
    for gene_id, chosen in canonical.items():
        assert chosen == [genes[gene_id]["canonical_transcript_id"]]


def test_lengths_count_both_ends(extracted):
    genes, _, features = extracted
    assert genes["GENE1"]["length"] == 600  # 100 to 699
    cds = next(f for f in features if f["feature_id"] == "TX1A_CDS_1")
    assert (cds["start"], cds["end"], cds["length"]) == (150, 199, 50)
