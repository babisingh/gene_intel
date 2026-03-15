#!/usr/bin/env python3
"""
Download BioMart domain annotation TSVs for all 14 Ensembl species.

Each file is saved as: data/biomart/biomart_<taxon_id>.tsv

BioMart REST API format:
  https://www.ensembl.org/biomart/martservice?query=<URL-encoded XML>

Attributes downloaded per species:
  - Gene stable ID     (ensembl_gene_id)
  - Pfam domain        (pfam)
  - InterPro accession (interpro)
  - GO term accession  (go_id)

These column headers match the DOMAIN_COLUMNS dict in biomart_parser.py.

Virtual schema differences per BioMart endpoint:
  www.ensembl.org     → virtualSchemaName="default"
  plants.ensembl.org  → virtualSchemaName="plants_mart"
  fungi.ensembl.org   → virtualSchemaName="fungi_mart"

Usage:
    python scripts/download_biomart.py                  # all species
    python scripts/download_biomart.py --species 9606   # single taxon ID
    python scripts/download_biomart.py --dry-run        # print URLs only
"""

import argparse
import os
import sys
import time
import urllib.parse
import urllib.request

BIOMART_DIR = os.environ.get("BIOMART_DATA_DIR", "./data/biomart")

# Download in 256 KB chunks so the connection stays alive for large species
CHUNK_SIZE = 256 * 1024

# BioMart can be very slow for large genomes; allow up to 20 minutes per file
DOWNLOAD_TIMEOUT = 1200  # seconds

# ── BioMart endpoints (base URL, virtualSchemaName) ───────────────────────────
_ENSEMBL        = ("https://www.ensembl.org/biomart/martservice",    "default")
_ENSEMBL_PLANTS = ("https://plants.ensembl.org/biomart/martservice", "plants_mart")
_ENSEMBL_FUNGI  = ("https://fungi.ensembl.org/biomart/martservice",  "fungi_mart")

# ── Species registry ───────────────────────────────────────────────────────────
# taxon_id → (endpoint_tuple, dataset_name, output_filename)
BIOMART_SPECIES = {
    # ── Main Ensembl (vertebrates + invertebrates) ─────────────────────────────
    "9606":   (_ENSEMBL,        "hsapiens_gene_ensembl",      "biomart_9606.tsv"),
    "10090":  (_ENSEMBL,        "mmusculus_gene_ensembl",     "biomart_10090.tsv"),
    "7955":   (_ENSEMBL,        "drerio_gene_ensembl",        "biomart_7955.tsv"),
    "9031":   (_ENSEMBL,        "ggallus_gene_ensembl",       "biomart_9031.tsv"),
    "8364":   (_ENSEMBL,        "xtropicalis_gene_ensembl",   "biomart_8364.tsv"),
    "9598":   (_ENSEMBL,        "ptroglodytes_gene_ensembl",  "biomart_9598.tsv"),
    "7227":   (_ENSEMBL,        "dmelanogaster_gene_ensembl", "biomart_7227.tsv"),
    "6239":   (_ENSEMBL,        "celegans_gene_ensembl",      "biomart_6239.tsv"),
    # ── EnsemblPlants (virtualSchemaName=plants_mart) ─────────────────────────
    "3702":   (_ENSEMBL_PLANTS, "athaliana_eg_gene",          "biomart_3702.tsv"),
    "4530":   (_ENSEMBL_PLANTS, "osativa_eg_gene",            "biomart_4530.tsv"),
    "3218":   (_ENSEMBL_PLANTS, "ppatens_eg_gene",            "biomart_3218.tsv"),
    "3055":   (_ENSEMBL_PLANTS, "creinhardtii_eg_gene",       "biomart_3055.tsv"),
    # ── EnsemblFungi (virtualSchemaName=fungi_mart) ───────────────────────────
    "162425": (_ENSEMBL_FUNGI,  "aniger_eg_gene",             "biomart_162425.tsv"),
    "4932":   (_ENSEMBL_FUNGI,  "scerevisiae_eg_gene",        "biomart_4932.tsv"),
    # E. coli (511145) excluded — uses GFF3 Dbxref instead of BioMart
}


def build_biomart_url(base_url: str, virtual_schema: str, dataset: str) -> str:
    """
    Build a BioMart REST API URL that streams a TSV with:
      Gene stable ID | Pfam domain | InterPro accession | GO term accession

    header="1"      → TSV includes column name row
    uniqueRows="1"  → deduplicates rows server-side
    """
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


def download_species(taxon_id: str, dry_run: bool = False) -> bool:
    """Download BioMart TSV for a single species. Returns True on success."""
    if taxon_id not in BIOMART_SPECIES:
        print(f"  SKIP {taxon_id}: not in BIOMART_SPECIES (E. coli uses GFF3)")
        return True

    (base_url, virtual_schema), dataset, filename = BIOMART_SPECIES[taxon_id]
    url = build_biomart_url(base_url, virtual_schema, dataset)
    outpath = os.path.join(BIOMART_DIR, filename)

    if dry_run:
        print(f"  DRY-RUN  taxon={taxon_id}  schema={virtual_schema}  dataset={dataset}")
        print(f"    URL : {url}")
        print(f"    OUT : {outpath}")
        return True

    if os.path.exists(outpath) and os.path.getsize(outpath) > 0:
        print(f"  ✓ {filename} already exists, skipping")
        return True

    print(f"  ↓ Downloading {filename} (schema={virtual_schema}, dataset={dataset})…")
    tmp_path = outpath + ".part"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "gene-intel/1.0"})
        with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp:
            # Validate the first chunk contains the expected TSV header before
            # committing to a full download.
            first_chunk = resp.read(512)
            first_line = first_chunk.split(b"\n", 1)[0].decode("utf-8", errors="replace")
            if "Gene stable ID" not in first_line and "Ensembl Gene ID" not in first_line:
                print(f"  ✗ {filename}: unexpected response — wrong dataset name or schema?")
                print(f"      First line: {first_line[:200]}")
                return False

            # Stream the rest chunk-by-chunk so the connection doesn't time out
            with open(tmp_path, "wb") as f:
                f.write(first_chunk)
                while True:
                    chunk = resp.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)

        os.rename(tmp_path, outpath)
        size_kb = os.path.getsize(outpath) // 1024
        print(f"  ✓ {filename} saved ({size_kb:,} KB)")
        return True

    except Exception as exc:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        print(f"  ✗ {filename}: {exc}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Download BioMart domain TSVs")
    parser.add_argument("--species", help="Single taxon ID to download (e.g. 9606)")
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
        # Be polite to Ensembl servers between requests
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
