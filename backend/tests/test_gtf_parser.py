"""
Tests for gtf_parser.py
"""

from app.ingestion.gtf_parser import parse_gtf_streaming, parse_ensembl_col9, parse_ncbi_col9


def test_parse_ensembl_gtf_yields_records(sample_human_gtf):
    records = list(parse_gtf_streaming(sample_human_gtf, "ensembl_gtf"))
    assert len(records) > 0


def test_ensembl_gene_record_has_expected_keys(sample_human_gtf):
    records = list(parse_gtf_streaming(sample_human_gtf, "ensembl_gtf"))
    gene_records = [r for r in records if r["feature_type"] == "gene"]
    assert len(gene_records) > 0

    gene = gene_records[0]
    assert "chromosome" in gene
    assert "start" in gene
    assert "end" in gene
    assert "strand" in gene
    assert "attributes" in gene
    assert "length" in gene
    # Coordinates are 1-based and include both ends
    assert gene["length"] == gene["end"] - gene["start"] + 1


def test_length_counts_both_ends(tmp_path):
    path = tmp_path / "codon.gtf"
    path.write_text('1\ttest\tstart_codon\t100\t102\t.\t+\t0\tgene_id "G"; transcript_id "T";\n')
    (record,) = parse_gtf_streaming(str(path), "ensembl_gtf")
    assert record["length"] == 3


def test_parse_ncbi_gff3_yields_records(sample_ecoli_gff3):
    records = list(parse_gtf_streaming(sample_ecoli_gff3, "ncbi_gff3"))
    assert len(records) > 0


def test_ncbi_gene_record_has_gene_id(sample_ecoli_gff3):
    records = list(parse_gtf_streaming(sample_ecoli_gff3, "ncbi_gff3"))
    gene_records = [r for r in records if r["feature_type"] == "gene"]
    assert len(gene_records) > 0

    gene = gene_records[0]
    attrs = gene["attributes"]
    assert "gene_id" in attrs


def test_parse_ensembl_col9_extracts_gene_id():
    col9 = 'gene_id "ENSG00000139618"; gene_name "BRCA2"; gene_biotype "protein_coding";'
    attrs = parse_ensembl_col9(col9)
    assert attrs["gene_id"] == "ENSG00000139618"
    assert attrs["gene_name"] == "BRCA2"
    assert attrs["gene_biotype"] == "protein_coding"


def test_parse_ensembl_col9_collects_db_xref():
    col9 = 'gene_id "ENSG001"; db_xref "Pfam:PF00082"; db_xref "GO:0001234";'
    attrs = parse_ensembl_col9(col9)
    assert isinstance(attrs["db_xref"], list)
    assert len(attrs["db_xref"]) == 2


def test_parse_ensembl_col9_collects_every_tag():
    # Only the last tag used to survive, and the canonical tag is often not last
    col9 = ('gene_id "ENSG001"; transcript_id "ENST001"; tag "basic"; '
            'tag "Ensembl_canonical"; tag "MANE_Select";')
    attrs = parse_ensembl_col9(col9)
    assert attrs["tag"] == ["basic", "Ensembl_canonical", "MANE_Select"]


def test_parse_ncbi_col9_extracts_fields():
    col9 = "ID=gene-b0001;Name=thrL;Dbxref=UniProtKB/Swiss-Prot:P0AD86,Pfam:PF01030"
    attrs = parse_ncbi_col9(col9)
    assert attrs["gene_id"] == "b0001"
    assert attrs["gene_name"] == "thrL"
    assert isinstance(attrs["db_xref"], list)
    assert "Pfam:PF01030" in attrs["db_xref"]


def test_parse_ncbi_col9_reads_ids_and_parents_as_gtf_keys():
    cds = parse_ncbi_col9("ID=cds-NP_414542.1;Parent=gene-b0001;protein_id=NP_414542.1")
    assert (cds["gene_id"], cds["ID"]) == ("b0001", "cds-NP_414542.1")
    assert "transcript_id" not in cds
    rna = parse_ncbi_col9("ID=rna-b0202;Parent=gene-b0202;gbkey=tRNA")
    assert (rna["transcript_id"], rna["gene_id"]) == ("rna-b0202", "b0202")
    exon = parse_ncbi_col9("ID=exon-b0202-1;Parent=rna-b0202")
    assert exon["transcript_id"] == "rna-b0202"
    assert "gene_id" not in exon


def test_gff3_rna_rows_are_kept(sample_ecoli_gff3):
    types = {r["feature_type"] for r in parse_gtf_streaming(sample_ecoli_gff3, "ncbi_gff3")}
    assert {"gene", "CDS", "exon", "tRNA", "ncRNA"} <= types
    assert not types & {"region", "pseudogene"}


def test_irrelevant_feature_types_are_skipped(sample_human_gtf):
    records = list(parse_gtf_streaming(sample_human_gtf, "ensembl_gtf"))
    feature_types = {r["feature_type"] for r in records}
    # "start_codon" and "stop_codon" may not appear in fixture but others should not
    allowed = {"gene", "transcript", "CDS", "exon", "UTR",
               "five_prime_utr", "three_prime_utr", "start_codon", "stop_codon"}
    assert feature_types.issubset(allowed)
