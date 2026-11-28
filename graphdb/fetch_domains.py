#!/usr/bin/env python3
"""
Fetch the protein domain annotations that the graph image loads.

Writes, under --out (graphdb/domains in the repo):
    <taxon>.tsv.gz  gene_id, source (Pfam or InterPro), accession: one row
                    per gene and domain, only for genes in the species' GTF
    names.tsv.gz    source, accession, description
    sources.json    what each file was made from, with row counts and
                    checksums, which graphdb/tests/test_domain_files.py checks

export_csv.py reads these files when the image is built and fetches nothing,
so a build does not depend on outside servers. Run this script only to
refresh them, for example after replacing a GTF file, and commit the result.

The sources match the GTF files in backend/data/gtf:

- Ensembl 111 and Ensembl Genomes 58 core databases, from the table dumps on
  the Ensembl FTP sites. Pfam: protein_feature rows of the "pfam" analysis.
  InterPro: the interpro table, which maps member database signatures (Pfam,
  SMART, PROSITE, PANTHER and others) to InterPro entries. A gene gets the
  domains of all its translations. Genes that are not in the GTF file (those
  on patches and haplotypes) are left out.
- Rice: the Ensembl Plants 58 database has Pfam hits for almost no genes, so
  rice comes from Ensembl Plants 63, whose gene IDs are all in the release 58
  GTF.
- E. coli K-12 has a RefSeq GFF3, not an Ensembl GTF. Its domains come from
  UniProt's reference proteome UP000000625, matched to genes by ordered locus
  name (b-number).
- Descriptions: Pfam-A.clans.tsv.gz and InterPro entry.list, newest release
  first, then older releases, which still name entries retired since.

Usage, from the repo root (about 260 MB of downloads; 8.5 minutes in
November 2026):
    python3 graphdb/fetch_domains.py --cache /tmp/gene-intel-domain-downloads

Downloads stay in --cache and are reused when the script runs again.
"""

from __future__ import annotations

import argparse
import collections
import datetime
import gzip
import hashlib
import http.client
import io
import json
import os
import re
import shutil
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
USER_AGENT = "gene-intel-fetch-domains/1.0"

ENSEMBL_111 = "https://ftp.ensembl.org/pub/release-111/mysql/"
PLANTS_58 = "https://ftp.ensemblgenomes.ebi.ac.uk/pub/plants/release-58/mysql/"
PLANTS_63 = "https://ftp.ensemblgenomes.ebi.ac.uk/pub/plants/release-63/mysql/"
FUNGI_58 = "https://ftp.ensemblgenomes.ebi.ac.uk/pub/fungi/release-58/mysql/"

# taxon: (GTF file in backend/data/gtf, FTP folder, core database)
ENSEMBL_SPECIES = {
    "9606": ("homo_sapiens.gtf.gz", ENSEMBL_111, "homo_sapiens_core_111_38"),
    "10090": ("mus_musculus.gtf.gz", ENSEMBL_111, "mus_musculus_core_111_39"),
    "7955": ("danio_rerio.gtf.gz", ENSEMBL_111, "danio_rerio_core_111_11"),
    "9031": ("gallus_gallus.gtf.gz", ENSEMBL_111, "gallus_gallus_core_111_7"),
    "8364": ("xenopus_tropicalis.gtf.gz", ENSEMBL_111, "xenopus_tropicalis_core_111_10"),
    "9598": ("pan_troglodytes.gtf.gz", ENSEMBL_111, "pan_troglodytes_core_111_3"),
    "7227": ("drosophila_melanogaster.gtf.gz", ENSEMBL_111,
             "drosophila_melanogaster_core_111_10"),
    "6239": ("caenorhabditis_elegans.gtf.gz", ENSEMBL_111,
             "caenorhabditis_elegans_core_111_282"),
    "3702": ("arabidopsis_thaliana.gtf.gz", PLANTS_58, "arabidopsis_thaliana_core_58_111_11"),
    "4530": ("oryza_sativa.gtf.gz", PLANTS_63, "oryza_sativa_core_63_116_7"),
    "3218": ("physcomitrium_patens.gtf.gz", PLANTS_58, "physcomitrium_patens_core_58_111_2"),
    "3055": ("chlamydomonas_reinhardtii.gtf.gz", PLANTS_58,
             "chlamydomonas_reinhardtii_core_58_111_3"),
    "162425": ("aspergillus_niger.gtf.gz", FUNGI_58, "aspergillus_niger_core_58_111_2"),
    "4932": ("saccharomyces_cerevisiae.gtf.gz", FUNGI_58,
             "saccharomyces_cerevisiae_core_58_111_4"),
}

ECOLI_TAXON = "511145"
ECOLI_GFF3 = "ecoli_k12.gff3.gz"
ECOLI_URL = "https://rest.uniprot.org/uniprotkb/stream?" + urllib.parse.urlencode({
    "query": "(proteome:UP000000625)",
    "fields": "accession,gene_oln,xref_pfam,xref_interpro",
    "format": "tsv",
    "compressed": "true",
})
ECOLI_HEADER = ["Entry", "Gene Names (ordered locus)", "Pfam", "InterPro"]

# Newest first: a description comes from the first release that has the entry.
# 38.0 is rice's Pfam release, 35.0 everyone else's. InterPro 107.0 names most
# of the entries in rice's annotation that were retired by 111.0; 97.0 and
# 96.0 are Ensembl 111's; 90.0 names the zebrafish entries retired since (its
# InterPro annotation dates from 2022).
PFAM_RELEASES = ["39.0", "38.0", "35.0"]
INTERPRO_RELEASES = ["111.0", "107.0", "97.0", "96.0", "90.0"]
EBI = "https://ftp.ebi.ac.uk/pub/databases/"

TABLES = ("analysis", "interpro", "gene", "transcript", "translation", "protein_feature")
ACCESSION = {"Pfam": re.compile(r"PF\d{5}"), "InterPro": re.compile(r"IPR\d{6}")}
HEADER = ("gene_id", "source", "accession")
NAMES_HEADER = ("source", "accession", "description")


def pfam_url(release: str) -> str:
    return f"{EBI}Pfam/releases/Pfam{release}/Pfam-A.clans.tsv.gz"


def interpro_url(release: str) -> str:
    return f"{EBI}interpro/releases/{release}/entry.list"


def download(url: str, dest: str) -> dict:
    """Fetch url into dest, or reuse dest from an earlier run. Returns what
    was recorded about the download: url, bytes, seconds, UniProt release."""
    record = dest + ".json"
    if os.path.exists(dest) and os.path.exists(record):
        with open(record, encoding="utf-8") as f:
            return json.load(f)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    for attempt in (1, 2, 3):
        start = time.monotonic()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=600) as resp, \
                    open(dest + ".part", "wb") as f:
                shutil.copyfileobj(resp, f, 1 << 20)
                release = resp.headers.get("X-UniProt-Release")
            break
        except (OSError, http.client.HTTPException) as exc:  # URLError is an OSError
            client_error = isinstance(exc, urllib.error.HTTPError) and exc.code < 500
            if client_error or attempt == 3:
                raise SystemExit(f"download failed: {url}: {exc}")
            print(f"  retrying {url}: {exc}", flush=True)
            time.sleep(20 * attempt)
    os.replace(dest + ".part", dest)
    info = {"url": url, "bytes": os.path.getsize(dest),
            "seconds": round(time.monotonic() - start, 1)}
    if release:
        info["uniprot_release"] = release
    with open(record, "w", encoding="utf-8") as f:
        json.dump(info, f)
    return info


def schema_columns(sql_gz: str) -> dict:
    """Column names of the tables read here, in dump order, from the
    database's CREATE TABLE statements."""
    with gzip.open(sql_gz, "rt", encoding="utf-8", errors="replace") as f:
        sql = f.read()
    columns = {}
    for table in TABLES:
        m = re.search(r"CREATE TABLE `%s` \((.*?)\n\)" % table, sql, re.S)
        if not m:
            raise SystemExit(f"{sql_gz}: no CREATE TABLE `{table}`")
        columns[table] = re.findall(r"^\s*`(\w+)`", m.group(1), re.M)
    return columns


def mysql_rows(path: str, columns: list, wanted: tuple):
    """The wanted fields of every row of a MySQL table dump: tab-separated,
    one row per line, and a newline inside a field follows a backslash."""
    picks = [columns.index(name) for name in wanted]
    pending = ""
    with gzip.open(path, "rt", encoding="utf-8", errors="replace", newline="\n") as f:
        for line in f:
            line = pending + line.rstrip("\n")
            if (len(line) - len(line.rstrip("\\"))) % 2:
                pending = line[:-1] + "\n"
                continue
            pending = ""
            fields = line.split("\t")
            if len(fields) != len(columns):
                raise SystemExit(f"{path}: a row has {len(fields)} fields, "
                                 f"the table has {len(columns)} columns")
            yield [fields[i] for i in picks]
    if pending:
        raise SystemExit(f"{path}: the file ends inside a row")


def ensembl_pairs(db_dir: str, columns: dict, gtf_genes: set):
    """(gene_id, source, accession) for the genes in gtf_genes, from one core
    database's dumps. Returns the pairs, the genes left out and the versions
    the database records for its Pfam and InterPro annotation."""
    def table(name, *wanted):
        return mysql_rows(os.path.join(db_dir, f"{name}.txt.gz"), columns[name], wanted)

    analyses = {aid: (logic, version) for aid, logic, version
                in table("analysis", "analysis_id", "logic_name", "db_version")}
    pfam = {aid for aid, (logic, _) in analyses.items() if logic == "pfam"}
    if not pfam:
        raise SystemExit(f"{db_dir}: no pfam analysis")
    versions = {"pfam_release": ", ".join(sorted({analyses[a][1] for a in pfam}))}
    interpro2go = sorted({v for logic, v in analyses.values() if logic == "interpro2go"})
    if interpro2go:
        versions["interpro2go"] = ", ".join(interpro2go)

    interpro = collections.defaultdict(set)
    for ipr, member in table("interpro", "interpro_ac", "id"):
        interpro[member].add(ipr)
    stable_id = dict(table("gene", "gene_id", "stable_id"))
    gene_of_transcript = dict(table("transcript", "transcript_id", "gene_id"))
    transcript_of_translation = dict(table("translation", "translation_id", "transcript_id"))

    pairs, left_out = set(), set()
    for translation, hit, aid in table("protein_feature",
                                       "translation_id", "hit_name", "analysis_id"):
        found = ([("Pfam", hit)] if aid in pfam else []) + \
            [("InterPro", ipr) for ipr in interpro.get(hit, ())]
        if not found:
            continue
        try:
            gene = stable_id[gene_of_transcript[transcript_of_translation[translation]]]
        except KeyError:
            raise SystemExit(f"{db_dir}: translation {translation} has no gene")
        if gene not in gtf_genes:
            left_out.add(gene)
            continue
        pairs.update((gene, source, accession) for source, accession in found)
    return pairs, left_out, versions


def ecoli_pairs(tsv_gz: str, gene_ids: set):
    """(gene_id, source, accession) from UniProt's TSV, one gene per b-number
    in the ordered locus names. Returns the pairs and the b-numbers left out."""
    pairs, left_out = set(), set()
    with gzip.open(tsv_gz, "rt", encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
        if header != ECOLI_HEADER:
            raise SystemExit(f"{tsv_gz}: columns {header}, expected {ECOLI_HEADER}")
        for line in f:
            _entry, loci, pfam, interpro = line.rstrip("\n").split("\t")
            for gene in (t for t in loci.split() if re.fullmatch(r"b\d{4}", t)):
                if gene not in gene_ids:
                    left_out.add(gene)
                    continue
                pairs.update((gene, "Pfam", a) for a in pfam.split(";") if a)
                pairs.update((gene, "InterPro", a) for a in interpro.split(";") if a)
    return pairs, left_out


def gtf_gene_ids(path: str) -> set:
    """gene_id of every gene row of an Ensembl GTF file."""
    ids = set()
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            fields = line.split("\t", 8)
            if len(fields) == 9 and fields[2] == "gene":
                m = re.search(r'gene_id "([^"]+)"', fields[8])
                if m:
                    ids.add(m.group(1))
    return ids


def gff3_gene_ids(path: str) -> set:
    """Gene IDs of an NCBI GFF3 file, read as the loader reads them:
    ID=gene-b0001 is gene b0001."""
    ids = set()
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            fields = line.split("\t", 8)
            if len(fields) == 9 and fields[2] == "gene":
                m = re.search(r"(?:^|;)ID=gene-([^;\s]+)", fields[8])
                if m:
                    ids.add(m.group(1))
    return ids


def read_names(pfam_files: list, interpro_files: list) -> dict:
    """{(source, accession): description}, from files listed newest first."""
    names = {}
    for path in pfam_files:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                fields = line.rstrip("\n").split("\t")
                if len(fields) >= 5 and ACCESSION["Pfam"].fullmatch(fields[0]):
                    names.setdefault(("Pfam", fields[0]), clean(fields[4]))
    for path in interpro_files:
        with open(path, encoding="utf-8") as f:
            header = f.readline().rstrip("\n").split("\t")
            if header[:3] != ["ENTRY_AC", "ENTRY_TYPE", "ENTRY_NAME"]:
                raise SystemExit(f"{path}: unexpected header {header}")
            for line in f:
                fields = line.rstrip("\n").split("\t")
                if len(fields) >= 3 and ACCESSION["InterPro"].fullmatch(fields[0]):
                    names.setdefault(("InterPro", fields[0]), clean(fields[2]))
    return names


def clean(text: str) -> str:
    """One line of text: tabs and newlines would break the TSV."""
    return " ".join(text.split())


def check_rows(what: str, pairs: set) -> None:
    for gene, source, accession in pairs:
        pattern = ACCESSION.get(source)
        if not gene or re.search(r"\s", gene) or not pattern or not pattern.fullmatch(accession):
            raise SystemExit(f"{what}: unexpected row {gene!r} {source!r} {accession!r}")


def gz_bytes(text: str) -> bytes:
    """gzip with no file name and no timestamp, so the bytes depend only on
    the text (and the zlib version)."""
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", fileobj=buf, mode="wb", compresslevel=9, mtime=0) as g:
        g.write(text.encode("utf-8"))
    return buf.getvalue()


def write_table(path: str, header: tuple, rows: list) -> dict:
    """Write rows as a gzipped TSV. Returns the row count and the SHA-256 of
    the uncompressed text."""
    text = "\t".join(header) + "\n" + "".join("\t".join(r) + "\n" for r in rows)
    with open(path + ".part", "wb") as f:
        f.write(gz_bytes(text))
    os.replace(path + ".part", path)
    return {"rows": len(rows), "tsv_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--gtf-dir", default=os.path.join(REPO, "backend", "data", "gtf"),
                    help="the GTF and GFF3 files the graph is built from")
    ap.add_argument("--out", default=os.path.join(HERE, "domains"),
                    help="where to write the domain files (default graphdb/domains)")
    ap.add_argument("--cache", default=os.path.join(tempfile.gettempdir(),
                                                    "gene-intel-domain-downloads"),
                    help="folder for the downloads, reused on the next run")
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)

    species, all_pairs = {}, {}
    for taxon, (gtf, base, db) in ENSEMBL_SPECIES.items():
        start = time.monotonic()
        folder = os.path.join(args.cache, db)
        got = [download(f"{base}{db}/{db}.sql.gz", os.path.join(folder, f"{db}.sql.gz"))]
        got += [download(f"{base}{db}/{t}.txt.gz", os.path.join(folder, f"{t}.txt.gz"))
                for t in TABLES]
        gtf_path = os.path.join(args.gtf_dir, gtf)
        pairs, left_out, versions = ensembl_pairs(
            folder, schema_columns(os.path.join(folder, f"{db}.sql.gz")), gtf_gene_ids(gtf_path))
        all_pairs[taxon] = pairs
        species[taxon] = {"source": f"{base}{db}/", **versions, "gtf": gtf,
                          "gtf_sha256": file_sha256(gtf_path),
                          "genes_not_in_gtf": len(left_out),
                          "download_bytes": sum(g["bytes"] for g in got)}
        print(f"{taxon:>7} {db}: {len(pairs)} rows, {len(left_out)} genes not in the GTF, "
              f"{time.monotonic() - start:.0f} s", flush=True)

    start = time.monotonic()
    gff3_path = os.path.join(args.gtf_dir, ECOLI_GFF3)
    got = download(ECOLI_URL, os.path.join(args.cache, "uniprot", "UP000000625.tsv.gz"))
    pairs, left_out = ecoli_pairs(os.path.join(args.cache, "uniprot", "UP000000625.tsv.gz"),
                                  gff3_gene_ids(gff3_path))
    all_pairs[ECOLI_TAXON] = pairs
    species[ECOLI_TAXON] = {"source": ECOLI_URL,
                            "uniprot_release": got.get("uniprot_release", "unknown"),
                            "gtf": ECOLI_GFF3, "gtf_sha256": file_sha256(gff3_path),
                            "genes_not_in_gtf": len(left_out), "download_bytes": got["bytes"]}
    print(f"{ECOLI_TAXON:>7} UniProt UP000000625: {len(pairs)} rows, {len(left_out)} genes "
          f"not in the GFF3, {time.monotonic() - start:.0f} s", flush=True)

    for taxon, pairs in all_pairs.items():
        check_rows(f"taxon {taxon}", pairs)
        info = write_table(os.path.join(args.out, f"{taxon}.tsv.gz"), HEADER, sorted(pairs))
        species[taxon].update(
            file=f"{taxon}.tsv.gz", genes=len({g for g, _, _ in pairs}),
            pfam=sum(1 for _, s, _ in pairs if s == "Pfam"),
            interpro=sum(1 for _, s, _ in pairs if s == "InterPro"), **info)

    pfam_files = []
    for release in PFAM_RELEASES:
        dest = os.path.join(args.cache, "names", f"Pfam{release}-A.clans.tsv.gz")
        download(pfam_url(release), dest)
        pfam_files.append(dest)
    interpro_files = []
    for release in INTERPRO_RELEASES:
        dest = os.path.join(args.cache, "names", f"interpro{release}.entry.list")
        download(interpro_url(release), dest)
        interpro_files.append(dest)
    names = read_names(pfam_files, interpro_files)
    used = sorted({(s, a) for pairs in all_pairs.values() for _, s, a in pairs})
    named = [(s, a, names[(s, a)]) for s, a in used if (s, a) in names]
    info = write_table(os.path.join(args.out, "names.tsv.gz"), NAMES_HEADER, named)

    sources = {
        "fetched": datetime.datetime.now(datetime.timezone.utc).date().isoformat(),
        "script": "graphdb/fetch_domains.py",
        "species": species,
        "names": {"file": "names.tsv.gz", **info, "accessions": len(used),
                  "unnamed": len(used) - len(named),
                  "pfam": [pfam_url(r) for r in PFAM_RELEASES],
                  "interpro": [interpro_url(r) for r in INTERPRO_RELEASES]},
    }
    with open(os.path.join(args.out, "sources.json"), "w", encoding="utf-8") as f:
        json.dump(sources, f, indent=1, sort_keys=True)
        f.write("\n")
    rows = sum(len(p) for p in all_pairs.values())
    print(f"{rows} rows for {len(all_pairs)} species, {len(used)} domains "
          f"({len(used) - len(named)} without a description), written to {args.out}", flush=True)


if __name__ == "__main__":
    main()
