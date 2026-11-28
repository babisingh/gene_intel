"""
Export the Gene-Intel graph as CSV files for `neo4j-admin database import`.

This writes the graph that `python -m app.ingestion.run_ingest --all
--step gtf` would write over Bolt, plus protein domains. It calls the
loader's own `ingest_species()` for every species, with the batch writers
swapped for functions that write CSV rows, so parsing and species metadata
come from the loader itself. The relationship rules follow the loader's
Cypher: a relationship is only written when the node it MATCHes exists.

Protein domains (Domain nodes and HAS_DOMAIN edges) come from the files in
graphdb/domains, which fetch_domains.py makes from Ensembl and UniProt. They
are committed, so the build reads them and fetches nothing. The loader's
own domain step (`--step domains`) does not run here, and the loader does
not read these files.

Usage (inside the image build, see graphdb/Dockerfile):
    python graphdb/export_csv.py --backend /src/backend --out /csv

Writes, under --out:
    species.csv genes.csv transcripts.csv features.csv [domains.csv]
    has_gene.csv has_transcript.csv has_feature.csv co_located_with.csv
    [has_domain.csv]
    schema.cypher   the constraints and indexes from app/db/schema.py
    manifest.json   node and relationship counts, checked after the import

Cross-species ID collisions are not merged here. The importer rejects
duplicate IDs, so a collision fails the build instead of silently diverging
from the loader's MERGE behaviour.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import shutil
import sys
from multiprocessing import get_context

DOMAINS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "domains")

NODE_COLUMNS = {
    "species": [("taxon_id", "ID(Species)"), ("name", ""), ("common_name", ""),
                ("assembly", ""), ("kingdom", ""), ("gtf_source", ""),
                ("ingested_at", "")],
    "genes": [("gene_id", "ID(Gene)"), ("name", ""), ("biotype", ""),
              ("chromosome", ""), ("start", "long"), ("end", "long"),
              ("strand", ""), ("length", "long"), ("species_taxon", ""),
              ("cds_length", "long"), ("exon_count", "long"),
              ("utr5_length", "long"), ("utr3_length", "long"),
              ("utr_cds_ratio", "double"), ("canonical_transcript_id", ""),
              ("canonical_source", "")],
    "transcripts": [("transcript_id", "ID(Transcript)"), ("gene_id", ""),
                    ("type", ""), ("exon_count", "long"),
                    ("cds_length", "long"),
                    ("support_level", "long"), ("is_canonical", "boolean")],
    "features": [("feature_id", "ID(Feature)"), ("transcript_id", ""),
                 ("type", ""), ("length", "long"), ("rank", "long"),
                 ("start", "long"), ("end", "long")],
    "domains": [("domain_id", "ID(Domain)"), ("source", ""),
                ("description", "")],
}

REL_HEADERS = {
    "has_gene": ":START_ID(Species),:END_ID(Gene)",
    "has_transcript": ":START_ID(Gene),:END_ID(Transcript)",
    "has_feature": ":START_ID(Transcript),:END_ID(Feature)",
    "has_domain": ":START_ID(Gene),:END_ID(Domain)",
    "co_located_with": ":START_ID(Gene),:END_ID(Gene),distance_bp:long",
}

LABELS = {"species": "Species", "genes": "Gene", "transcripts": "Transcript",
          "features": "Feature", "domains": "Domain"}
REL_TYPES = {"has_gene": "HAS_GENE", "has_transcript": "HAS_TRANSCRIPT",
             "has_feature": "HAS_FEATURE", "has_domain": "HAS_DOMAIN",
             "co_located_with": "CO_LOCATED_WITH"}


def cell(value) -> str:
    """One CSV field. None stays empty, which the importer treats as unset,
    the same as `SET n += row` with a null value. Strings are always quoted
    so that an empty string stays an empty string."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    return '"' + str(value).replace('"', '""') + '"'


def header(kind: str) -> str:
    return ",".join(f"{name}:{typ}" if typ else name
                    for name, typ in NODE_COLUMNS[kind])


def _check_header(path: str, line: str, expected: list) -> None:
    if line.rstrip("\n").split("\t") != expected:
        raise SystemExit(f"{path}: columns {line.strip()!r}, expected {expected}")


def read_domain_names(domains_dir: str) -> dict:
    """{(source, accession): description} from names.tsv.gz."""
    path = os.path.join(domains_dir, "names.tsv.gz")
    names = {}
    with gzip.open(path, "rt", encoding="utf-8") as f:
        _check_header(path, f.readline(), ["source", "accession", "description"])
        for line in f:
            source, accession, description = line.rstrip("\n").split("\t")
            names[(source, accession)] = description
    return names


def read_gene_domains(domains_dir: str, taxon_id: str, names: dict) -> list:
    """One species' rows from <taxon>.tsv.gz, in the shape the loader's
    domain parsers hand to write_domains_batch(). The domain ID is
    `Source:accession`, as the BioMart parser writes it."""
    path = os.path.join(domains_dir, f"{taxon_id}.tsv.gz")
    if not os.path.exists(path):
        return []
    rows = []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        _check_header(path, f.readline(), ["gene_id", "source", "accession"])
        for line in f:
            gene_id, source, accession = line.rstrip("\n").split("\t")
            rows.append({"gene_id": gene_id, "domain_id": f"{source}:{accession}",
                         "source": source,
                         "description": names.get((source, accession), "")})
    return rows


class _NullSession:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _NullDriver:
    """Stands in for the Neo4j driver: ingest_species() only opens a session
    and hands it to the batch writers, which are replaced below."""

    def session(self):
        return _NullSession()


def _export_one(job):
    """Run the loader's ingest_species() for one species, writing CSV parts,
    then add the species' domains from domains_dir."""
    order, taxon_id, parts_dir, domains_dir = job

    from app.ingestion import run_ingest

    meta = run_ingest.SPECIES_REGISTRY[taxon_id]
    gtf_path = os.path.join(run_ingest.settings.gtf_data_dir, meta["gtf_filename"])
    if not os.path.exists(gtf_path):
        return {"taxon_id": taxon_id, "skipped": f"GTF file not found: {gtf_path}"}

    files = {}

    def out(kind):
        if kind not in files:
            os.makedirs(os.path.join(parts_dir, kind), exist_ok=True)
            path = os.path.join(parts_dir, kind, f"{order:03d}_{taxon_id}.csv")
            files[kind] = open(path, "w", encoding="utf-8", newline="")
        return files[kind]

    counts = {k: 0 for k in list(NODE_COLUMNS) + list(REL_HEADERS)}
    species_ids, gene_ids, transcript_ids = set(), set(), set()
    domains = {}
    has_domain, edges = set(), {}

    def write_nodes(kind, rows):
        names = [name for name, _ in NODE_COLUMNS[kind]]
        expected = set(names)
        f = out(kind)
        for row in rows:
            if set(row) != expected:
                raise SystemExit(
                    f"{kind} row keys changed: {sorted(row)} != {sorted(expected)}. "
                    "Update NODE_COLUMNS in graphdb/export_csv.py to match the loader.")
            f.write(",".join(cell(row[n]) for n in names) + "\n")
            counts[kind] += 1

    def write_rel(kind, start, end, *props):
        out(kind).write(",".join([cell(start), cell(end)] + [cell(p) for p in props]) + "\n")
        counts[kind] += 1

    # The loader's Cypher, mirrored row by row (see batch_writer.py).
    def species_node(_session, species):
        write_nodes("species", [species])
        species_ids.add(species["taxon_id"])

    def genes_batch(_session, genes):
        write_nodes("genes", genes)
        for g in genes:
            gene_ids.add(g["gene_id"])
            if g["species_taxon"] in species_ids:          # MATCH (s:Species ...)
                write_rel("has_gene", g["species_taxon"], g["gene_id"])

    def transcripts_batch(_session, transcripts):
        write_nodes("transcripts", transcripts)
        for t in transcripts:
            transcript_ids.add(t["transcript_id"])
            if t["gene_id"] in gene_ids:                    # MATCH (g:Gene ...)
                write_rel("has_transcript", t["gene_id"], t["transcript_id"])

    def features_batch(_session, features):
        write_nodes("features", features)
        for feat in features:
            if feat["transcript_id"] in transcript_ids:     # MATCH (t:Transcript ...)
                write_rel("has_feature", feat["transcript_id"], feat["feature_id"])

    def domains_batch(_session, gene_domains):
        for d in gene_domains:
            # MERGE (d:Domain) SET source, description: the last row wins
            domains[d["domain_id"]] = {"domain_id": d["domain_id"],
                                       "source": d["source"],
                                       "description": d["description"]}
            if d["gene_id"] in gene_ids:                    # MATCH (g:Gene ...)
                has_domain.add((d["gene_id"], d["domain_id"]))

    def edges_batch(_session, rows):
        for e in rows:
            if e["from_id"] in gene_ids and e["to_id"] in gene_ids:
                # MERGE (a)-[r:CO_LOCATED_WITH]-(b) is undirected: an existing
                # pair keeps its direction, SET updates the distance.
                key = frozenset((e["from_id"], e["to_id"]))
                if key in edges:
                    edges[key] = (edges[key][0], edges[key][1], e["distance_bp"])
                else:
                    edges[key] = (e["from_id"], e["to_id"], e["distance_bp"])

    run_ingest.write_species_node = species_node
    run_ingest.write_genes_batch = genes_batch
    run_ingest.write_transcripts_batch = transcripts_batch
    run_ingest.write_features_batch = features_batch
    run_ingest.write_domains_batch = domains_batch
    run_ingest.write_edges_batch = edges_batch

    run_ingest.ingest_species(taxon_id, _NullDriver())

    # Domains from graphdb/domains. Rows for genes that the loader did not
    # write are dropped before the MERGE, so every Domain node has a gene.
    gene_domains = read_gene_domains(domains_dir, taxon_id, read_domain_names(domains_dir))
    known = [d for d in gene_domains if d["gene_id"] in gene_ids]
    if len(known) < len(gene_domains):
        print(f"taxon {taxon_id}: skipped {len(gene_domains) - len(known)} domain rows "
              "for genes that are not in the graph", flush=True)
    domains_batch(None, known)

    for start, end, distance in edges.values():
        write_rel("co_located_with", start, end, distance)
    for gene_id, domain_id in sorted(has_domain):
        write_rel("has_domain", gene_id, domain_id)
    for f in files.values():
        f.close()

    return {"taxon_id": taxon_id, "counts": counts,
            "domains": list(domains.values())}


def _concat(parts, dest, head):
    with open(dest, "w", encoding="utf-8", newline="") as d:
        d.write(head + "\n")
        for p in parts:
            with open(p, encoding="utf-8") as s:
                shutil.copyfileobj(s, d, 1 << 20)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--backend", required=True, help="path to the repo's backend/ folder")
    ap.add_argument("--out", required=True, help="output folder for the CSV files")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--domains", default=DOMAINS_DIR,
                    help="folder with the domain files (default: graphdb/domains)")
    args = ap.parse_args()

    domains_dir = os.path.abspath(args.domains)
    if not os.path.isfile(os.path.join(domains_dir, "names.tsv.gz")):
        raise SystemExit(f"No domain files in {domains_dir}. See graphdb/fetch_domains.py.")

    backend = os.path.abspath(args.backend)
    # Same locations the loader reads, set before app.config is imported.
    os.environ["GTF_DATA_DIR"] = os.path.join(backend, "data", "gtf")
    os.environ["BIOMART_DATA_DIR"] = os.path.join(backend, "data", "biomart")
    sys.path.insert(0, backend)

    from app.db.schema import CONSTRAINTS, INDEXES
    from app.ingestion.run_ingest import SPECIES_REGISTRY

    out = os.path.abspath(args.out)
    parts_dir = os.path.join(out, "_parts")
    os.makedirs(parts_dir, exist_ok=True)

    jobs = [(i, taxon, parts_dir, domains_dir) for i, taxon in enumerate(SPECIES_REGISTRY)]
    with get_context("fork").Pool(args.workers, maxtasksperchild=1) as pool:
        results = pool.map(_export_one, jobs, chunksize=1)

    loaded = [r for r in results if "counts" in r]
    for r in results:
        if "skipped" in r:
            print(f"skipped taxon {r['taxon_id']}: {r['skipped']}", flush=True)

    totals = {k: sum(r["counts"][k] for r in loaded)
              for k in list(NODE_COLUMNS) + list(REL_HEADERS)}

    # Domain nodes are MERGEd globally, in registry order: the last row wins.
    domains = {}
    for r in loaded:
        for d in r["domains"]:
            domains[d["domain_id"]] = d
    totals["domains"] = len(domains)
    if domains:
        os.makedirs(os.path.join(parts_dir, "domains"), exist_ok=True)
        with open(os.path.join(parts_dir, "domains", "all.csv"), "w",
                  encoding="utf-8", newline="") as f:
            for d in domains.values():
                f.write(",".join(cell(d[n]) for n, _ in NODE_COLUMNS["domains"]) + "\n")

    written = []
    for kind in list(NODE_COLUMNS) + list(REL_HEADERS):
        folder = os.path.join(parts_dir, kind)
        parts = sorted(os.path.join(folder, p) for p in os.listdir(folder)) \
            if os.path.isdir(folder) else []
        if totals[kind] == 0:
            continue
        head = header(kind) if kind in NODE_COLUMNS else REL_HEADERS[kind]
        _concat(parts, os.path.join(out, f"{kind}.csv"), head)
        written.append(kind)
    shutil.rmtree(parts_dir)

    with open(os.path.join(out, "schema.cypher"), "w", encoding="utf-8") as f:
        for stmt in CONSTRAINTS + INDEXES:
            f.write(stmt.rstrip(";") + ";\n")

    manifest = {
        "nodes": {LABELS[k]: totals[k] for k in NODE_COLUMNS},
        "relationships": {REL_TYPES[k]: totals[k] for k in REL_HEADERS},
        "files": written,
        "species": {r["taxon_id"]: r["counts"]["genes"] for r in loaded},
        "constraints": len(CONSTRAINTS),
        "indexes": len(INDEXES),
    }
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    print(json.dumps(manifest, indent=1), flush=True)


if __name__ == "__main__":
    main()
