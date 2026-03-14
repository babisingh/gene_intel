#!/usr/bin/env python3
"""
Download BioMart domain annotation TSVs for all 14 Ensembl species.

Each file is saved as: data/biomart/biomart_<taxon_id>.tsv

BioMart REST API format:
  https://www.ensembl.org/biomart/martservice?query=<URL-encoded XML>

Attributes downloaded per species:
  - Gene stable ID    (ensembl_gene_id)
  - Pfam domain       (pfam)
  - InterPro accession (interpro)
  - GO term accession  (go_id)

These column headers match the DOMAIN_COLUMNS dict in biomart_parser.py.

For EnsemblGenomes species (Plants, Fungi) the base URL changes but the
XML format is identical.

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

# ── BioMart base URLs ──────────────────────────────────────────────────────────
ENSEMBL_BIOMART     = "https://www.ensembl.org/biomart/martservice"
ENSEMBL_PLANTS      = "https://plants.ensembl.org/biomart/martservice"
ENSEMBL_FUNGI       = "https://fungi.ensembl.org/biomart/martservice"

# ── Species registry: taxon_id → (biomart_base_url, dataset_name, output_filename)
BIOMART_SPECIES = {
    "9606":   (ENSEMBL_BIOMART,  "hsapiens_gene_ensembl",   "biomart_9606.tsv"),
    "10090":  (ENSEMBL_BIOMART,  "mmusculus_gene_ensembl",  "biomart_10090.tsv"),
    "7955":   (ENSEMBL_BIOMART,  "drerio_gene_ensembl",     "biomart_7955.tsv"),
    "9031":   (ENSEMBL_BIOMART,  "ggallus_gene_ensembl",    "biomart_9031.tsv"),
    "8364":   (ENSEMBL_BIOMART,  "xtropicalis_gene_ensembl","biomart_8364.tsv"),
    "9598":   (ENSEMBL_BIOMART,  "ptroglodytes_gene_ensembl","biomart_9598.tsv"),
    "7227":   (ENSEMBL_BIOMART,  "dmelanogaster_gene_ensembl","biomart_7227.tsv"),
    "6239":   (ENSEMBL_BIOMART,  "celegans_gene_ensembl",   "biomart_6239.tsv"),
    # EnsemblPlants
    "3702":   (ENSEMBL_PLANTS,   "athaliana_eg_gene",       "biomart_3702.tsv"),
    "4530":   (ENSEMBL_PLANTS,   "osativa_eg_gene",         "biomart_4530.tsv"),
    "3218":   (ENSEMBL_PLANTS,   "ppatens_eg_gene",         "biomart_3218.tsv"),
    "3055":   (ENSEMBL_PLANTS,   "creinhardtii_eg_gene",    "biomart_3055.tsv"),
    # EnsemblFungi
    "162425": (ENSEMBL_FUNGI,    "aniger_eg_gene",          "biomart_162425.tsv"),
    "4932":   (ENSEMBL_FUNGI,    "scerevisiae_eg_gene",     "biomart_4932.tsv"),
    # E. coli (511145) is excluded — uses GFF3 Dbxref instead of BioMart
}


def build_biomart_url(base_url: str, dataset: str) -> str:
    """
    Build a BioMart REST API URL that downloads a TSV with:
      Gene stable ID | Pfam domain | InterPro accession | GO term accession

    The XML query uses header=1 so the TSV includes column names.
    uniqueRows=1 removes duplicate rows.
    """
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<!DOCTYPE Query>'
        '<Query virtualSchemaName="default" formatter="TSV" header="1" '
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

    base_url, dataset, filename = BIOMART_SPECIES[taxon_id]
    url = build_biomart_url(base_url, dataset)
    outpath = os.path.join(BIOMART_DIR, filename)

    if dry_run:
        print(f"  DRY-RUN taxon={taxon_id} dataset={dataset}")
        print(f"    URL : {url}")
        print(f"    OUT : {outpath}")
        return True

    if os.path.exists(outpath) and os.path.getsize(outpath) > 0:
        print(f"  ✓ {filename} already exists, skipping")
        return True

    print(f"  ↓ Downloading {filename} (dataset={dataset})…")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "gene-intel/1.0"})
        with urllib.request.urlopen(req, timeout=300) as resp:
            content = resp.read()

        # BioMart returns an HTML error page if the dataset name is wrong.
        # Check that the response looks like a TSV (first line should be the header).
        first_line = content.split(b"\n", 1)[0].decode("utf-8", errors="replace")
        if "Gene stable ID" not in first_line and "Ensembl Gene ID" not in first_line:
            print(f"  ✗ {filename}: unexpected response (wrong dataset name?)")
            print(f"      First line: {first_line[:200]}")
            return False

        with open(outpath, "wb") as f:
            f.write(content)
        rows = content.count(b"\n")
        print(f"  ✓ {filename} saved ({rows:,} lines)")
        return True

    except Exception as exc:
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
        # Be polite to the Ensembl servers
        if not args.dry_run and i < len(targets):
            time.sleep(2)

    print()
    if failed:
        print(f"✗ Failed: {failed}")
        sys.exit(1)
    else:
        print("✓ All downloads complete")
        if not args.dry_run:
            print(f"Next: cd backend && python -m app.ingestion.run_ingest --all")


if __name__ == "__main__":
    main()
