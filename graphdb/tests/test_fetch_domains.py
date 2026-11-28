"""
fetch_domains.py turns Ensembl table dumps and UniProt's TSV into the files in
graphdb/domains. These tests run it on small hand-made inputs, offline.
"""

import gzip
import hashlib
import json
import os

import pytest

# The real tables have more columns, in other places: the script finds the
# ones it reads by name, from the CREATE TABLE statements.
SCHEMA = """\
CREATE TABLE `analysis` (
  `analysis_id` smallint(5) unsigned NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `logic_name` varchar(128) NOT NULL,
  `db_version` varchar(40) DEFAULT NULL,
  PRIMARY KEY (`analysis_id`)
) ENGINE=MyISAM;
CREATE TABLE `interpro` (
  `interpro_ac` varchar(40) NOT NULL,
  `id` varchar(40) NOT NULL,
  UNIQUE KEY `accession_idx` (`interpro_ac`,`id`)
) ENGINE=MyISAM;
CREATE TABLE `gene` (
  `gene_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `description` text,
  `stable_id` varchar(128) DEFAULT NULL,
  PRIMARY KEY (`gene_id`)
) ENGINE=MyISAM;
CREATE TABLE `transcript` (
  `transcript_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `gene_id` int(10) unsigned DEFAULT NULL,
  PRIMARY KEY (`transcript_id`)
) ENGINE=MyISAM;
CREATE TABLE `translation` (
  `translation_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `transcript_id` int(10) unsigned NOT NULL,
  PRIMARY KEY (`translation_id`)
) ENGINE=MyISAM;
CREATE TABLE `protein_feature` (
  `protein_feature_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `translation_id` int(10) unsigned NOT NULL,
  `hit_name` varchar(40) NOT NULL,
  `analysis_id` smallint(5) unsigned NOT NULL,
  PRIMARY KEY (`protein_feature_id`)
) ENGINE=MyISAM;
"""

TABLES = {
    "analysis": "1\t\\N\tpfam\t35.0\n2\t\\N\tsmart\t9.0\n3\t\\N\tinterpro2go\t2023-05-09\n"
                "4\t\\N\tncoils\t\\N\n",
    "interpro": "IPR000719\tPF00069\nIPR011009\tPF00069\nIPR000719\tSM00220\n"
                "IPR001245\tPF07714\n",
    # GENE_A's description holds a newline, which MySQL writes after a backslash
    "gene": "1\tkinase\\\nsecond line\tGENE_A\n2\t\\N\tGENE_B\n3\t\\N\tPATCH_GENE\n",
    "transcript": "10\t1\n11\t1\n20\t2\n30\t3\n",
    "translation": "100\t10\n101\t11\n200\t20\n300\t30\n",
    "protein_feature": "1\t100\tPF00069\t1\n2\t101\tSM00220\t2\n3\t200\tPF07714\t1\n"
                       "4\t200\tCoil\t4\n5\t300\tPF00069\t1\n",
}

GTF = (
    '#!genome-build test\n'
    '1\tensembl\tgene\t1\t100\t.\t+\t.\tgene_id "GENE_A"; gene_biotype "protein_coding";\n'
    '1\tensembl\ttranscript\t1\t100\t.\t+\t.\tgene_id "PATCH_GENE"; transcript_id "T1";\n'
    '1\tensembl\tgene\t200\t300\t.\t-\t.\tgene_id "GENE_B"; gene_biotype "protein_coding";\n'
)

EXPECTED_PAIRS = {
    ("GENE_A", "Pfam", "PF00069"), ("GENE_A", "InterPro", "IPR000719"),
    ("GENE_A", "InterPro", "IPR011009"), ("GENE_B", "Pfam", "PF07714"),
    ("GENE_B", "InterPro", "IPR001245"),
}

GFF3 = (
    "##gff-version 3\n"
    "NC_000913.3\tRefSeq\tgene\t337\t2799\t.\t+\t.\tID=gene-b0002;Name=thrA;Dbxref=GeneID:945803\n"
    "NC_000913.3\tRefSeq\tCDS\t337\t2799\t.\t+\t0\tID=cds-NP_414543.1;Parent=gene-b0002\n"
    "NC_000913.3\tRefSeq\tgene\t2801\t3733\t.\t+\t.\tID=gene-b0003;Name=thrB\n"
    "NC_000913.3\tRefSeq\tgene\t4000\t5000\t.\t+\t.\tID=gene-b4143;Name=groS\n"
    "NC_000913.3\tRefSeq\tCDS\t6000\t7000\t.\t+\t0\tID=cds-X;Parent=gene-b4144\n"
)

UNIPROT = (
    "Entry\tGene Names (ordered locus)\tPfam\tInterPro\n"
    "P00561\tb0002 JW0001\tPF00696;PF00742;\tIPR001048;IPR005106;\n"
    "P0A6F9\tb4143 b4144\tPF00166;\tIPR020818;\n"
    "P99999\tJW9999\tPF00001;\t\n"
    "P00547\tb0003\t\t\n"
)


def write_dumps(folder, write_gz):
    os.makedirs(folder, exist_ok=True)
    write_gz(os.path.join(folder, "test_core.sql.gz"), SCHEMA)
    for table, text in TABLES.items():
        write_gz(os.path.join(folder, f"{table}.txt.gz"), text)


def test_ensembl_pairs_follow_translations_to_genes_in_the_gtf(tmp_path, write_gz,
                                                                fetch_domains):
    db = tmp_path / "test_core"
    write_dumps(str(db), write_gz)
    columns = fetch_domains.schema_columns(str(db / "test_core.sql.gz"))
    genes = fetch_domains.gtf_gene_ids(write_gz(tmp_path / "test.gtf.gz", GTF))
    assert genes == {"GENE_A", "GENE_B"}

    pairs, left_out, versions = fetch_domains.ensembl_pairs(str(db), columns, genes)

    assert pairs == EXPECTED_PAIRS
    assert left_out == {"PATCH_GENE"}
    assert versions == {"pfam_release": "35.0", "interpro2go": "2023-05-09"}


def test_a_row_with_the_wrong_number_of_fields_stops_the_run(tmp_path, write_gz,
                                                              fetch_domains):
    path = write_gz(tmp_path / "translation.txt.gz", "100\t10\n101\t11\textra\n")
    with pytest.raises(SystemExit, match="2 columns"):
        list(fetch_domains.mysql_rows(path, ["translation_id", "transcript_id"],
                                      ("translation_id",)))


def test_ecoli_pairs_by_b_number(tmp_path, write_gz, fetch_domains):
    genes = fetch_domains.gff3_gene_ids(write_gz(tmp_path / "ecoli.gff3.gz", GFF3))
    assert genes == {"b0002", "b0003", "b4143"}

    pairs, left_out = fetch_domains.ecoli_pairs(write_gz(tmp_path / "up.tsv.gz", UNIPROT),
                                                genes)

    assert pairs == {
        ("b0002", "Pfam", "PF00696"), ("b0002", "Pfam", "PF00742"),
        ("b0002", "InterPro", "IPR001048"), ("b0002", "InterPro", "IPR005106"),
        ("b4143", "Pfam", "PF00166"), ("b4143", "InterPro", "IPR020818"),
    }
    assert left_out == {"b4144"}


def test_names_come_from_the_newest_release_that_has_the_entry(tmp_path, write_gz,
                                                               fetch_domains):
    pfam_new = write_gz(tmp_path / "pfam_new.tsv.gz",
                        "PF00069\tCL0016\tPKinase\tPkinase\tProtein kinase domain\n")
    pfam_old = write_gz(tmp_path / "pfam_old.tsv.gz",
                        "PF00069\tCL0016\tPKinase\tPkinase\tOld name\n"
                        "PF99999\t\t\tRetired\tA retired family\n")
    ipr_new = tmp_path / "ipr_new.list"
    ipr_new.write_text("ENTRY_AC\tENTRY_TYPE\tENTRY_NAME\n"
                       "IPR000719\tDomain\tProtein kinase domain\n")
    ipr_old = tmp_path / "ipr_old.list"
    ipr_old.write_text("ENTRY_AC\tENTRY_TYPE\tENTRY_NAME\n"
                       "IPR000719\tDomain\tOld kinase name\n"
                       "IPR099999\tFamily\tRetired  entry\n")

    names = fetch_domains.read_names([pfam_new, pfam_old], [str(ipr_new), str(ipr_old)])

    assert names == {
        ("Pfam", "PF00069"): "Protein kinase domain",
        ("Pfam", "PF99999"): "A retired family",
        ("InterPro", "IPR000719"): "Protein kinase domain",
        ("InterPro", "IPR099999"): "Retired entry",
    }


def test_output_bytes_depend_only_on_the_rows(tmp_path, fetch_domains):
    rows = sorted(EXPECTED_PAIRS)
    a = fetch_domains.write_table(str(tmp_path / "a.tsv.gz"), fetch_domains.HEADER, rows)
    b = fetch_domains.write_table(str(tmp_path / "b.tsv.gz"), fetch_domains.HEADER, rows)

    data = (tmp_path / "a.tsv.gz").read_bytes()
    assert data == (tmp_path / "b.tsv.gz").read_bytes()
    assert data[4:8] == b"\0\0\0\0"                      # no timestamp
    text = gzip.decompress(data)
    assert a == b == {"rows": 5, "tsv_sha256": hashlib.sha256(text).hexdigest()}
    assert text.decode().splitlines()[0] == "gene_id\tsource\taccession"


def test_main_writes_the_files_and_sources(tmp_path, write_gz, monkeypatch, fetch_domains):
    """The whole run, with download() serving the inputs above."""
    base, db = "https://ensembl.invalid/mysql/", "test_core"
    served = {f"{base}{db}/{db}.sql.gz": SCHEMA, fetch_domains.ECOLI_URL: UNIPROT}
    served.update({f"{base}{db}/{t}.txt.gz": text for t, text in TABLES.items()})
    served[fetch_domains.pfam_url("2.0")] = "PF00069\t\t\tPkinase\tProtein kinase domain\n"
    served[fetch_domains.pfam_url("1.0")] = (
        "PF07714\t\t\tPK_Tyr\tTyrosine kinase\nPF00696\t\t\tAA_kinase\tAA kinase\n"
        "PF00742\t\t\tHomoserine_dh\tHomoserine dehydrogenase\n"
        "PF00166\t\t\tCpn10\tChaperonin 10 Kd subunit\n")
    served[fetch_domains.interpro_url("2.0")] = (
        "ENTRY_AC\tENTRY_TYPE\tENTRY_NAME\nIPR000719\tDomain\tProtein kinase domain\n")
    served[fetch_domains.interpro_url("1.0")] = (
        "ENTRY_AC\tENTRY_TYPE\tENTRY_NAME\nIPR011009\tHomologous_superfamily\t"
        "Protein kinase-like domain superfamily\n")

    def fake_download(url, dest):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if dest.endswith(".gz"):
            write_gz(dest, served[url])
        else:
            with open(dest, "w", encoding="utf-8") as f:
                f.write(served[url])
        info = {"url": url, "bytes": os.path.getsize(dest), "seconds": 0.0}
        if url == fetch_domains.ECOLI_URL:
            info["uniprot_release"] = "2026_04"
        return info

    monkeypatch.setattr(fetch_domains, "download", fake_download)
    monkeypatch.setattr(fetch_domains, "ENSEMBL_SPECIES", {"9606": ("homo.gtf.gz", base, db)})
    monkeypatch.setattr(fetch_domains, "PFAM_RELEASES", ["2.0", "1.0"])
    monkeypatch.setattr(fetch_domains, "INTERPRO_RELEASES", ["2.0", "1.0"])
    gtf_dir, out = tmp_path / "gtf", tmp_path / "out"
    gtf_dir.mkdir()
    write_gz(gtf_dir / "homo.gtf.gz", GTF)
    write_gz(gtf_dir / fetch_domains.ECOLI_GFF3, GFF3)

    fetch_domains.main(["--gtf-dir", str(gtf_dir), "--out", str(out),
                        "--cache", str(tmp_path / "cache")])

    assert sorted(os.listdir(out)) == ["511145.tsv.gz", "9606.tsv.gz", "names.tsv.gz",
                                       "sources.json"]
    with gzip.open(out / "9606.tsv.gz", "rt") as f:
        assert f.read() == "gene_id\tsource\taccession\n" + "".join(
            "\t".join(r) + "\n" for r in sorted(EXPECTED_PAIRS))
    with gzip.open(out / "names.tsv.gz", "rt") as f:
        names = f.read().splitlines()
    assert names[0] == "source\taccession\tdescription"
    assert "Pfam\tPF00069\tProtein kinase domain" in names
    assert not any("\tIPR001245\t" in n for n in names)      # no name in any release
    sources = json.loads((out / "sources.json").read_text())
    human, ecoli = sources["species"]["9606"], sources["species"]["511145"]
    assert human["source"] == f"{base}{db}/"
    assert (human["rows"], human["genes"], human["pfam"], human["interpro"]) == (5, 2, 2, 3)
    assert human["genes_not_in_gtf"] == 1
    assert human["pfam_release"] == "35.0"
    assert ecoli["uniprot_release"] == "2026_04"
    assert (ecoli["rows"], ecoli["genes_not_in_gtf"]) == (6, 1)
    # IPR001245, IPR001048, IPR005106 and IPR020818 are in no names file
    assert (sources["names"]["accessions"], sources["names"]["unnamed"]) == (11, 4)
