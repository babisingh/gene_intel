"""
Tests for feature_extractor.py on NCBI GFF3, the format E. coli K-12 comes in.

fixtures/sample_ecoli.gff3 holds real rows of backend/data/gtf/ecoli_k12.gff3.gz.
Its protein-coding genes have no transcript rows: each CDS row names its
gene as Parent. A GFF3 CDS includes the stop codon and a GTF CDS does not,
so the extractor moves those 3 bp into a stop_codon feature.
"""

import os

import pytest

from app.ingestion.feature_extractor import extract_features
from app.ingestion.gtf_parser import parse_gtf_streaming

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_ecoli.gff3")


@pytest.fixture(scope="module")
def extracted():
    genes, transcripts, features = extract_features(
        parse_gtf_streaming(FIXTURE, "ncbi_gff3"), "511145")
    return ({g["gene_id"]: g for g in genes},
            {t["transcript_id"]: t for t in transcripts},
            features)


def parts(features, transcript_id):
    """A transcript's features as {type: [(start, end), ...]} in rank order."""
    found = {}
    for f in sorted(features, key=lambda f: f["rank"]):
        if f["transcript_id"] == transcript_id:
            found.setdefault(f["type"], []).append((f["start"], f["end"]))
    return found


def test_a_protein_becomes_a_transcript_named_by_its_protein_id(extracted):
    genes, transcripts, _ = extracted
    transcript = transcripts["NP_414542.1"]
    assert transcript["gene_id"] == "b0001"
    assert transcript["type"] == "protein_coding"
    assert transcript["is_canonical"] is True
    assert genes["b0001"]["canonical_transcript_id"] == "NP_414542.1"
    assert genes["b0001"]["canonical_source"] == "longest_cds"


def test_the_stop_codon_leaves_the_cds(extracted):
    # thrL: the GFF3 CDS row 190-255 is 66 bp, 21 codons and the stop codon
    genes, transcripts, features = extracted
    assert parts(features, "NP_414542.1") == {
        "exon": [(190, 255)],
        "CDS": [(190, 252)],
        "start_codon": [(190, 192)],
        "stop_codon": [(253, 255)],
    }
    gene = genes["b0001"]
    assert gene["cds_length"] == 63 == transcripts["NP_414542.1"]["cds_length"]
    assert gene["exon_count"] == 1
    assert gene["utr5_length"] == gene["utr3_length"] == 0
    assert gene["utr_cds_ratio"] == 0.0
    # thrA: 337-2799 is 2,463 bp, 820 codons and the stop codon
    assert genes["b0002"]["cds_length"] == 2460


def test_on_the_minus_strand_the_stop_codon_is_at_the_low_end(extracted):
    # yaaA: the GFF3 CDS row 5683-6459, minus strand
    _, _, features = extracted
    assert parts(features, "NP_414547.1") == {
        "exon": [(5683, 6459)],
        "CDS": [(5686, 6459)],
        "start_codon": [(6457, 6459)],
        "stop_codon": [(5683, 5685)],
    }


def test_each_protein_of_a_gene_is_a_transcript_and_the_longest_cds_wins(extracted):
    # dnaX makes tau (NP_415003.1) and, by ribosomal slippage, the shorter
    # gamma (YP_009518751.1, two CDS rows)
    genes, transcripts, _ = extracted
    own = sorted(t for t, row in transcripts.items() if row["gene_id"] == "b0470")
    assert own == ["NP_415003.1", "YP_009518751.1"]
    assert transcripts["NP_415003.1"]["cds_length"] == 1929      # 643 codons
    assert transcripts["YP_009518751.1"]["cds_length"] == 1293   # 431 codons
    gene = genes["b0470"]
    assert gene["canonical_transcript_id"] == "NP_415003.1"
    assert gene["cds_length"] == 1929     # tau's alone, not tau's plus gamma's
    assert gene["exon_count"] == 1
    assert [t for t in own if transcripts[t]["is_canonical"]] == ["NP_415003.1"]


def test_a_slipped_cds_keeps_both_rows_in_one_exon(extracted):
    genes, _, features = extracted
    # gamma, plus strand: the second row reads base 493375 again
    assert parts(features, "YP_009518751.1") == {
        "exon": [(492092, 493386)],
        "CDS": [(492092, 493375), (493375, 493383)],
        "start_codon": [(492092, 492094)],
        "stop_codon": [(493384, 493386)],
    }
    # prfB, minus strand: the second row skips base 3036207
    assert parts(features, "NP_417367.1") == {
        "exon": [(3035184, 3036282)],
        "CDS": [(3036208, 3036282), (3035187, 3036206)],
        "start_codon": [(3036280, 3036282)],
        "stop_codon": [(3035184, 3035186)],
    }
    assert genes["b2891"]["cds_length"] == 1095    # 365 codons
    assert genes["b2891"]["exon_count"] == 1


def test_a_trna_row_is_a_transcript_with_its_exon(extracted):
    genes, transcripts, features = extracted
    transcript = transcripts["rna-b0202"]
    assert transcript["gene_id"] == "b0202"
    assert transcript["type"] == "tRNA"
    assert parts(features, "rna-b0202") == {"exon": [(225381, 225457)]}
    gene = genes["b0202"]
    assert gene["canonical_transcript_id"] == "rna-b0202"
    assert gene["canonical_source"] == "longest_transcript"
    assert (gene["cds_length"], gene["exon_count"], gene["utr_cds_ratio"]) == (0, 1, None)


def test_a_noncoding_gene_takes_its_longest_rna(extracted):
    # istR: IstR-2 (rna-b4616) is 140 bp, IstR-1 (rna-b4616-2) 73 bp
    genes, transcripts, _ = extracted
    assert transcripts["rna-b4616-2"]["type"] == "ncRNA"
    assert genes["b4616"]["canonical_transcript_id"] == "rna-b4616"
    assert transcripts["rna-b4616-2"]["is_canonical"] is False


def test_a_pseudogene_cds_makes_no_transcript(extracted):
    # crl (b0240) is a pseudogene row, and those are not loaded as genes
    genes, transcripts, features = extracted
    assert "b0240" not in genes
    assert all(t["gene_id"] in genes for t in transcripts.values())
    assert all(f["transcript_id"] in transcripts for f in features)


def test_a_gene_with_nothing_under_it_keeps_empty_values(extracted):
    # ssrA (b2621) has no RNA row in this file
    gene = extracted[0]["b2621"]
    assert (gene["cds_length"], gene["exon_count"]) == (0, 0)
    assert gene["canonical_transcript_id"] is None
    assert gene["canonical_source"] is None


def test_feature_ids_are_unique(extracted):
    ids = [f["feature_id"] for f in extracted[2]]
    assert len(ids) == len(set(ids))


def test_a_partial_cds_keeps_every_base_and_gets_no_codons(tmp_path):
    path = tmp_path / "partial.gff3"
    path.write_text(
        "##gff-version 3\n"
        "chr\tRefSeq\tgene\t100\t200\t.\t+\t.\tID=gene-p1;Name=p1;gene_biotype=protein_coding\n"
        "chr\tRefSeq\tCDS\t100\t200\t.\t+\t0\tID=cds-XP_1.1;Parent=gene-p1;"
        "end_range=200,.;partial=true;protein_id=XP_1.1\n"
    )
    genes, _, features = extract_features(parse_gtf_streaming(str(path), "ncbi_gff3"), "1")
    assert {f["type"] for f in features} == {"exon", "CDS"}
    assert genes[0]["cds_length"] == 101
