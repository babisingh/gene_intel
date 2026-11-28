"""
export_csv.py adds the files in graphdb/domains to the export: Domain nodes
with descriptions from names.tsv.gz, and HAS_DOMAIN edges for the genes the
loader wrote. The fixture GTF has two human genes, DDX11L1 and OR4F5.
"""

import gzip
import os
import shutil
import sys

import pytest

from app.ingestion import run_ingest

FIXTURE_GTF = os.path.join(os.path.dirname(__file__), "..", "..", "backend", "tests",
                           "fixtures", "sample_human.gtf")
WRITERS = ("write_species_node", "write_genes_batch", "write_transcripts_batch",
           "write_features_batch", "write_domains_batch", "write_edges_batch")
OR4F5 = "ENSG00000186092"
BRCA2 = "ENSG00000139618"          # not in the fixture GTF


@pytest.fixture
def export_human(tmp_path, monkeypatch, write_gz, export_csv):
    gtf_dir = tmp_path / "gtf"
    gtf_dir.mkdir()
    with open(FIXTURE_GTF, "rb") as src, gzip.open(gtf_dir / "homo_sapiens.gtf.gz", "wb") as dst:
        shutil.copyfileobj(src, dst)
    domains = tmp_path / "domains"
    domains.mkdir()
    write_gz(domains / "9606.tsv.gz", "gene_id\tsource\taccession\n"
             f"{BRCA2}\tPfam\tPF09103\n"
             f"{OR4F5}\tInterPro\tIPR000276\n"
             f"{OR4F5}\tInterPro\tIPR017452\n"
             f"{OR4F5}\tPfam\tPF13853\n")
    write_gz(domains / "names.tsv.gz", "source\taccession\tdescription\n"
             "InterPro\tIPR000276\tG protein-coupled receptor, rhodopsin-like\n"
             'Pfam\tPF13853\tOlfactory receptor "7tm_4"\n'
             "Pfam\tPF09103\tBRCA2, oligonucleotide/oligosaccharide-binding, domain 1\n")
    # _export_one swaps the loader's batch writers; put them back afterwards
    for name in WRITERS:
        monkeypatch.setattr(run_ingest, name, getattr(run_ingest, name))
    monkeypatch.setattr(run_ingest.settings, "gtf_data_dir", str(gtf_dir))
    parts = tmp_path / "parts"
    result = export_csv._export_one((0, "9606", str(parts), str(domains)))
    return result, parts


def test_domains_become_nodes_and_edges(export_human, export_csv):
    result, parts = export_human

    assert result["counts"]["genes"] == 2
    assert result["counts"]["has_domain"] == 3
    domains = sorted(result["domains"], key=lambda d: d["domain_id"])
    assert domains == [
        {"domain_id": "InterPro:IPR000276", "source": "InterPro",
         "description": "G protein-coupled receptor, rhodopsin-like"},
        {"domain_id": "InterPro:IPR017452", "source": "InterPro", "description": ""},
        {"domain_id": "Pfam:PF13853", "source": "Pfam",
         "description": 'Olfactory receptor "7tm_4"'},
    ]
    names = {name for name, _ in export_csv.NODE_COLUMNS["domains"]}
    assert all(set(d) == names for d in domains)
    with open(parts / "has_domain" / "000_9606.csv", encoding="utf-8") as f:
        assert f.read().splitlines() == [
            f'"{OR4F5}","InterPro:IPR000276"',
            f'"{OR4F5}","InterPro:IPR017452"',
            f'"{OR4F5}","Pfam:PF13853"',
        ]


def test_rows_for_genes_not_in_the_graph_make_no_domain_node(export_human):
    result, _ = export_human
    assert "Pfam:PF09103" not in {d["domain_id"] for d in result["domains"]}


def test_a_domain_csv_row_keeps_commas_and_quotes(export_csv):
    row = {"domain_id": "Pfam:PF13853", "source": "Pfam",
           "description": 'Olfactory receptor "7tm_4", family'}
    line = ",".join(export_csv.cell(row[n]) for n, _ in export_csv.NODE_COLUMNS["domains"])
    assert line == '"Pfam:PF13853","Pfam","Olfactory receptor ""7tm_4"", family"'


def test_export_stops_without_domain_files(tmp_path, monkeypatch, export_csv):
    monkeypatch.setattr(sys, "argv", ["export_csv.py", "--backend", "backend",
                                      "--out", str(tmp_path / "csv"),
                                      "--domains", str(tmp_path / "missing")])
    with pytest.raises(SystemExit, match="No domain files"):
        export_csv.main()
