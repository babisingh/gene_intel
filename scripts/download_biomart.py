#!/usr/bin/env python3
"""
Download BioMart domain annotation TSVs for all 14 Ensembl species.

Each file is saved as: data/biomart/biomart_<taxon_id>.tsv

Why BioMart and not FTP:
  Ensembl FTP TSV exports only contain gene→UniProt/Entrez/RefSeq xrefs.
  Pfam and InterPro domain annotations are only available via BioMart.

Download strategy:
  Uses `wget` subprocess with --timeout=0 (no idle timeout) which handles
  BioMart's slow initial response much better than Python urllib.
  Falls back to three BioMart mirrors if the primary times out.

Attributes downloaded per species:
  Gene stable ID | Pfam domain | InterPro accession | GO term accession

These column headers match the DOMAIN_COLUMNS dict in biomart_parser.py.

Virtual schema per endpoint:
  www.ensembl.org     → default
  plants.ensembl.org  → plants_mart
  fungi.ensembl.org   → fungi_mart

Usage:
    python scripts/download_biomart.py                  # all species
    python scripts/download_biomart.py --species 9606   # single taxon ID
    python scripts/download_biomart.py --dry-run        # print URLs only
"""

import argparse
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

BIOMART_DIR = os.environ.get("BIOMART_DATA_DIR", "./data/biomart")

# BioMart mirrors — tried in order on failure
_MIRRORS_MAIN   = [
    "https://www.ensembl.org/biomart/martservice",
    "https://useast.ensembl.org/biomart/martservice",
    "https://asia.ensembl.org/biomart/martservice",
]
_MIRRORS_PLANTS = ["https://plants.ensembl.org/biomart/martservice"]
_MIRRORS_FUNGI  = ["https://fungi.ensembl.org/biomart/martservice"]

# Endpoint config: (list_of_mirror_urls, virtualSchemaName)
_ENSEMBL        = (_MIRRORS_MAIN,   "default")
_ENSEMBL_PLANTS = (_MIRRORS_PLANTS, "plants_mart")
_ENSEMBL_FUNGI  = (_MIRRORS_FUNGI,  "fungi_mart")

# ── Species registry ───────────────────────────────────────────────────────────
BIOMART_SPECIES = {
    # Main Ensembl (vertebrates + invertebrates)
    "9606":   (_ENSEMBL,        "hsapiens_gene_ensembl",      "biomart_9606.tsv"),
    "10090":  (_ENSEMBL,        "mmusculus_gene_ensembl",     "biomart_10090.tsv"),
    "7955":   (_ENSEMBL,        "drerio_gene_ensembl",        "biomart_7955.tsv"),
    "9031":   (_ENSEMBL,        "ggallus_gene_ensembl",       "biomart_9031.tsv"),
    "8364":   (_ENSEMBL,        "xtropicalis_gene_ensembl",   "biomart_8364.tsv"),
    "9598":   (_ENSEMBL,        "ptroglodytes_gene_ensembl",  "biomart_9598.tsv"),
    "7227":   (_ENSEMBL,        "dmelanogaster_gene_ensembl", "biomart_7227.tsv"),
    "6239":   (_ENSEMBL,        "celegans_gene_ensembl",      "biomart_6239.tsv"),
    # EnsemblPlants (virtualSchemaName=plants_mart)
    "3702":   (_ENSEMBL_PLANTS, "athaliana_eg_gene",          "biomart_3702.tsv"),
    "4530":   (_ENSEMBL_PLANTS, "osativa_eg_gene",            "biomart_4530.tsv"),
    "3218":   (_ENSEMBL_PLANTS, "ppatens_eg_gene",            "biomart_3218.tsv"),
    "3055":   (_ENSEMBL_PLANTS, "creinhardtii_eg_gene",       "biomart_3055.tsv"),
    # EnsemblFungi (virtualSchemaName=fungi_mart)
    "162425": (_ENSEMBL_FUNGI,  "aniger_eg_gene",             "biomart_162425.tsv"),
    "4932":   (_ENSEMBL_FUNGI,  "scerevisiae_eg_gene",        "biomart_4932.tsv"),
    # E. coli (511145) excluded — uses GFF3 Dbxref instead of BioMart
}


def build_biomart_url(base_url: str, virtual_schema: str, dataset: str) -> str:
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<!DOCTYPE Query>'
        f'<Query virtualSchemaName="{virtual_schema}" formatter="TSV" header="1" '
        'uniqueRows="1" count="" datasetConfigVersion="0.6">'
        f'<Dataset name="{dataset}" interface="default">'
        '<Attribute name="ensembl_gene_id"/>'
        '<Attribute name="pfam"/>'
        '<Attribute name="interpro"/>'
        '<Attribute name="go_id"/>'
        '</Dataset>'
        '</Query>'
    )
    return f"{base_url}?query={urllib.parse.quote(xml)}"


def _validate_tsv(path: str) -> bool:
    """Return True if the file starts with the expected TSV header."""
    try:
        with open(path, "r", errors="replace") as f:
            first_line = f.readline()
        return "Gene stable ID" in first_line or "Ensembl Gene ID" in first_line
    except Exception:
        return False


def _wget_download(url: str, outpath: str) -> bool:
    """
    Download url → outpath using wget.
    --timeout=0     disables idle timeout (BioMart can take minutes to start)
    --tries=2       one retry on network error
    --server-response shows HTTP status in stderr for debugging
    Returns True on success.
    """
    tmp = outpath + ".part"
    try:
        result = subprocess.run(
            [
                "wget",
                "--quiet",
                "--timeout=0",      # no idle timeout
                "--tries=2",
                "--server-response",
                "-O", tmp,
                url,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # Surface wget's stderr so the user can see what went wrong
            err = (result.stderr or "").strip().splitlines()
            short_err = "\n      ".join(err[-5:]) if err else "wget failed"
            print(f"    wget exit {result.returncode}: {short_err}")
            if os.path.exists(tmp):
                os.remove(tmp)
            return False

        if not _validate_tsv(tmp):
            with open(tmp, "r", errors="replace") as f:
                first_line = f.readline().strip()
            print(f"    unexpected content (wrong dataset/schema?)")
            print(f"    first line: {first_line[:200]}")
            os.remove(tmp)
            return False

        os.rename(tmp, outpath)
        size_kb = os.path.getsize(outpath) // 1024
        print(f"  ✓ saved ({size_kb:,} KB)")
        return True

    except FileNotFoundError:
        print("    wget not found — falling back to urllib")
        if os.path.exists(tmp):
            os.remove(tmp)
        return None  # signal to use fallback


def _urllib_download(url: str, outpath: str) -> bool:
    """urllib fallback with no socket timeout and chunked streaming."""
    import socket
    tmp = outpath + ".part"
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(None)  # disable timeout entirely
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "gene-intel/1.0"})
        with urllib.request.urlopen(req) as resp:
            first_chunk = resp.read(512)
            first_line = first_chunk.split(b"\n", 1)[0].decode("utf-8", errors="replace")
            if "Gene stable ID" not in first_line and "Ensembl Gene ID" not in first_line:
                print(f"    unexpected content: {first_line[:200]}")
                return False
            with open(tmp, "wb") as f:
                f.write(first_chunk)
                while True:
                    chunk = resp.read(256 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
        os.rename(tmp, outpath)
        size_kb = os.path.getsize(outpath) // 1024
        print(f"  ✓ saved ({size_kb:,} KB)")
        return True
    except Exception as exc:
        if os.path.exists(tmp):
            os.remove(tmp)
        print(f"    urllib error: {exc}")
        return False
    finally:
        socket.setdefaulttimeout(old_timeout)


def download_species(taxon_id: str, dry_run: bool = False) -> bool:
    if taxon_id not in BIOMART_SPECIES:
        print(f"  SKIP {taxon_id}: not in registry (E. coli uses GFF3)")
        return True

    (mirrors, virtual_schema), dataset, filename = BIOMART_SPECIES[taxon_id]
    outpath = os.path.join(BIOMART_DIR, filename)

    if dry_run:
        url = build_biomart_url(mirrors[0], virtual_schema, dataset)
        print(f"  DRY-RUN  schema={virtual_schema}  dataset={dataset}")
        print(f"    URL : {url}")
        print(f"    OUT : {outpath}")
        return True

    if os.path.exists(outpath) and os.path.getsize(outpath) > 0:
        print(f"  ✓ {filename} already exists, skipping")
        return True

    for i, mirror in enumerate(mirrors, 1):
        url = build_biomart_url(mirror, virtual_schema, dataset)
        label = f"mirror {i}/{len(mirrors)}: {mirror.split('/')[2]}"
        print(f"  ↓ {filename}  ({label})  dataset={dataset}")

        result = _wget_download(url, outpath)
        if result is None:
            # wget not available — use urllib once
            result = _urllib_download(url, outpath)
        if result:
            return True

        if i < len(mirrors):
            print(f"  ↺ retrying with next mirror…")
            time.sleep(5)

    print(f"  ✗ all mirrors failed for {filename}")
    return False


def main():
    parser = argparse.ArgumentParser(description="Download BioMart domain TSVs")
    parser.add_argument("--species", help="Single taxon ID (e.g. 9606)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print URLs and output paths without downloading")
    args = parser.parse_args()

    os.makedirs(BIOMART_DIR, exist_ok=True)

    targets = [args.species] if args.species else list(BIOMART_SPECIES.keys())
    print(f"=== BioMart download: {len(targets)} species → {BIOMART_DIR} ===\n")

    failed = []
    for i, taxon_id in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] taxon={taxon_id}")
        ok = download_species(taxon_id, dry_run=args.dry_run)
        if not ok:
            failed.append(taxon_id)
        if not args.dry_run and i < len(targets):
            time.sleep(3)

    print()
    if failed:
        print(f"✗ Failed ({len(failed)}): {failed}")
        sys.exit(1)
    else:
        print("✓ All downloads complete")
        if not args.dry_run:
            print("Next: cd backend && python -m app.ingestion.run_ingest --all")


if __name__ == "__main__":
    main()
