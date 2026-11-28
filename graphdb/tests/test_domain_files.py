"""
The committed files in graphdb/domains, which the image build loads.

Each file must match what sources.json says fetch_domains.py wrote, and must
have been made for the GTF file that is in backend/data/gtf now: after a GTF
file is replaced, these tests fail until graphdb/fetch_domains.py has been
run again for the matching release.
"""

import gzip
import hashlib
import json
import os
import re

import pytest

from app.ingestion.run_ingest import SPECIES_REGISTRY

GRAPHDB = os.path.join(os.path.dirname(__file__), "..")
DOMAINS = os.path.join(GRAPHDB, "domains")
GTF_DIR = os.path.join(GRAPHDB, "..", "backend", "data", "gtf")
BIO_DICTIONARY = os.path.join(GRAPHDB, "..", "backend", "app", "agents", "bio_dictionary.py")
ACCESSION = {"Pfam": re.compile(r"PF\d{5}"), "InterPro": re.compile(r"IPR\d{6}")}

with open(os.path.join(DOMAINS, "sources.json"), encoding="utf-8") as _f:
    SOURCES = json.load(_f)


def read(name):
    """The uncompressed bytes of a domain file, and its lines."""
    with gzip.open(os.path.join(DOMAINS, name), "rb") as f:
        data = f.read()
    return data, data.decode("utf-8").splitlines()


@pytest.fixture(scope="module")
def species_rows():
    """{taxon: [(gene_id, source, accession), ...]}"""
    return {taxon: [tuple(line.split("\t")) for line in read(info["file"])[1][1:]]
            for taxon, info in SOURCES["species"].items()}


def test_every_species_with_a_gtf_file_has_domains():
    with_gtf = {taxon for taxon, meta in SPECIES_REGISTRY.items()
                if os.path.exists(os.path.join(GTF_DIR, meta["gtf_filename"]))}
    assert set(SOURCES["species"]) == with_gtf
    for taxon, info in SOURCES["species"].items():
        assert info["gtf"] == SPECIES_REGISTRY[taxon]["gtf_filename"]


def test_the_folder_holds_only_the_listed_files():
    listed = {info["file"] for info in SOURCES["species"].values()}
    assert set(os.listdir(DOMAINS)) == listed | {"names.tsv.gz", "sources.json"}


@pytest.mark.parametrize("taxon", sorted(SOURCES["species"]))
def test_species_file_matches_its_sources_entry(taxon):
    info = SOURCES["species"][taxon]
    data, lines = read(info["file"])
    assert hashlib.sha256(data).hexdigest() == info["tsv_sha256"]
    assert lines[0] == "gene_id\tsource\taccession"
    rows = [tuple(line.split("\t")) for line in lines[1:]]
    assert len(rows) == info["rows"]
    assert rows == sorted(set(rows)), "rows must be sorted and unique"
    for gene, source, accession in rows:
        assert gene and ACCESSION[source].fullmatch(accession), (gene, source, accession)
    assert sum(1 for r in rows if r[1] == "Pfam") == info["pfam"]
    assert sum(1 for r in rows if r[1] == "InterPro") == info["interpro"]
    assert len({r[0] for r in rows}) == info["genes"]


@pytest.mark.parametrize("taxon", sorted(SOURCES["species"]))
def test_species_file_was_made_for_the_current_gtf(taxon):
    info = SOURCES["species"][taxon]
    h = hashlib.sha256()
    with open(os.path.join(GTF_DIR, info["gtf"]), "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    assert h.hexdigest() == info["gtf_sha256"], (
        f"{info['gtf']} changed after graphdb/domains was fetched: rerun "
        "graphdb/fetch_domains.py with the release that matches the new file")


def test_names_file(species_rows):
    info = SOURCES["names"]
    data, lines = read(info["file"])
    assert hashlib.sha256(data).hexdigest() == info["tsv_sha256"]
    assert lines[0] == "source\taccession\tdescription"
    names = [tuple(line.split("\t")) for line in lines[1:]]
    assert len(names) == info["rows"]
    keys = [(s, a) for s, a, _ in names]
    assert keys == sorted(set(keys))
    used = {(s, a) for rows in species_rows.values() for _, s, a in rows}
    assert set(keys) <= used
    assert (len(used), len(used) - len(keys)) == (info["accessions"], info["unnamed"])
    assert {k for k in used if k[0] == "Pfam"} <= set(keys), "every Pfam domain has a name"


def test_known_domains(species_rows):
    brca2 = {(s, a) for g, s, a in species_rows["9606"] if g == "ENSG00000139618"}
    assert {a for s, a in brca2 if s == "Pfam"} == {
        "PF00634", "PF09103", "PF09104", "PF09121", "PF09169"}
    assert {a for s, a in brca2 if s == "InterPro"} == {
        "IPR002093", "IPR012340", "IPR015187", "IPR015188", "IPR015205", "IPR015252",
        "IPR015525", "IPR036315"}
    thra = {(s, a) for g, s, a in species_rows["511145"] if g == "b0002"}
    assert {a for s, a in thra if s == "Pfam"} == {"PF00696", "PF00742", "PF03447", "PF22468"}


def test_the_bio_dictionary_domains_are_on_some_gene(species_rows):
    """Every domain ID the Bio-Dictionary searches for exists in the graph."""
    with open(BIO_DICTIONARY, encoding="utf-8") as f:
        wanted = set(re.findall(r"'((?:Pfam|InterPro):[A-Z0-9]+)'", f.read()))
    assert wanted
    present = {f"{s}:{a}" for rows in species_rows.values() for _, s, a in rows}
    assert wanted <= present, sorted(wanted - present)
