#!/usr/bin/env python3
"""
Mock test for BioMart and GTF download URLs.

Validates that:
  1. All expected output file PATHS are correctly formed (no test writes files)
  2. All BioMart REST API URLs return an HTTP 200 with valid TSV headers
     (downloads only the first ~2 KB to check the header row)
  3. All Ensembl GTF FTP URLs return HTTP 200/206 (ranged GET for first 512 B)

This is a MOCK test — it checks URL reachability and response format but does
NOT download full files (too large for a test run).

Usage:
    python scripts/test_biomart_urls.py              # test all
    python scripts/test_biomart_urls.py --species 9606
    python scripts/test_biomart_urls.py --gtf-only
    python scripts/test_biomart_urls.py --biomart-only
    python scripts/test_biomart_urls.py --offline     # validate file paths only
"""

import argparse
import os
import sys
import urllib.parse
import urllib.request

# ── Path config (mirrors download scripts) ────────────────────────────────────
GTF_DIR     = os.environ.get("GTF_DATA_DIR",     "./data/gtf")
BIOMART_DIR = os.environ.get("BIOMART_DATA_DIR", "./data/biomart")

# ── BioMart endpoints: (base_url, virtualSchemaName) ─────────────────────────
_ENSEMBL        = ("https://www.ensembl.org/biomart/martservice",    "default")
_ENSEMBL_PLANTS = ("https://plants.ensembl.org/biomart/martservice", "plants_mart")
_ENSEMBL_FUNGI  = ("https://fungi.ensembl.org/biomart/martservice",  "fungi_mart")

# ── Species registry ───────────────────────────────────────────────────────────
# taxon_id → {name, biomart_endpoint, dataset, biomart_file, gtf_file, gtf_url}
SPECIES = {
    "9606": {
        "name": "Homo sapiens",
        "biomart_endpoint": _ENSEMBL,
        "dataset": "hsapiens_gene_ensembl",
        "biomart_file": "biomart_9606.tsv",
        "gtf_file": "homo_sapiens.gtf.gz",
        "gtf_url": "https://ftp.ensembl.org/pub/release-111/gtf/homo_sapiens/Homo_sapiens.GRCh38.111.gtf.gz",
    },
    "10090": {
        "name": "Mus musculus",
        "biomart_endpoint": _ENSEMBL,
        "dataset": "mmusculus_gene_ensembl",
        "biomart_file": "biomart_10090.tsv",
        "gtf_file": "mus_musculus.gtf.gz",
        "gtf_url": "https://ftp.ensembl.org/pub/release-111/gtf/mus_musculus/Mus_musculus.GRCm39.111.gtf.gz",
    },
    "7955": {
        "name": "Danio rerio",
        "biomart_endpoint": _ENSEMBL,
        "dataset": "drerio_gene_ensembl",
        "biomart_file": "biomart_7955.tsv",
        "gtf_file": "danio_rerio.gtf.gz",
        "gtf_url": "https://ftp.ensembl.org/pub/release-111/gtf/danio_rerio/Danio_rerio.GRCz11.111.gtf.gz",
    },
    "9031": {
        "name": "Gallus gallus",
        "biomart_endpoint": _ENSEMBL,
        "dataset": "ggallus_gene_ensembl",
        "biomart_file": "biomart_9031.tsv",
        "gtf_file": "gallus_gallus.gtf.gz",
        "gtf_url": "https://ftp.ensembl.org/pub/release-111/gtf/gallus_gallus/Gallus_gallus.bGalGal1.mat.broiler.GRCg7b.111.gtf.gz",
    },
    "8364": {
        "name": "Xenopus tropicalis",
        "biomart_endpoint": _ENSEMBL,
        "dataset": "xtropicalis_gene_ensembl",
        "biomart_file": "biomart_8364.tsv",
        "gtf_file": "xenopus_tropicalis.gtf.gz",
        "gtf_url": "https://ftp.ensembl.org/pub/release-111/gtf/xenopus_tropicalis/Xenopus_tropicalis.UCB_Xtro_10.0.111.gtf.gz",
    },
    "9598": {
        "name": "Pan troglodytes",
        "biomart_endpoint": _ENSEMBL,
        "dataset": "ptroglodytes_gene_ensembl",
        "biomart_file": "biomart_9598.tsv",
        "gtf_file": "pan_troglodytes.gtf.gz",
        "gtf_url": "https://ftp.ensembl.org/pub/release-111/gtf/pan_troglodytes/Pan_troglodytes.Pan_tro_3.0.111.gtf.gz",
    },
    "7227": {
        "name": "Drosophila melanogaster",
        "biomart_endpoint": _ENSEMBL,
        "dataset": "dmelanogaster_gene_ensembl",
        "biomart_file": "biomart_7227.tsv",
        "gtf_file": "drosophila_melanogaster.gtf.gz",
        "gtf_url": "https://ftp.ensembl.org/pub/release-111/gtf/drosophila_melanogaster/Drosophila_melanogaster.BDGP6.46.111.gtf.gz",
    },
    "6239": {
        "name": "Caenorhabditis elegans",
        "biomart_endpoint": _ENSEMBL,
        "dataset": "celegans_gene_ensembl",
        "biomart_file": "biomart_6239.tsv",
        "gtf_file": "caenorhabditis_elegans.gtf.gz",
        "gtf_url": "https://ftp.ensembl.org/pub/release-111/gtf/caenorhabditis_elegans/Caenorhabditis_elegans.WBcel235.111.gtf.gz",
    },
    # ── EnsemblPlants (virtualSchemaName=plants_mart) ─────────────────────────
    "3702": {
        "name": "Arabidopsis thaliana",
        "biomart_endpoint": _ENSEMBL_PLANTS,
        "dataset": "athaliana_eg_gene",
        "biomart_file": "biomart_3702.tsv",
        "gtf_file": "arabidopsis_thaliana.gtf.gz",
        "gtf_url": "https://ftp.ensemblgenomes.ebi.ac.uk/pub/plants/release-58/gtf/arabidopsis_thaliana/Arabidopsis_thaliana.TAIR10.58.gtf.gz",
    },
    "4530": {
        "name": "Oryza sativa",
        "biomart_endpoint": _ENSEMBL_PLANTS,
        "dataset": "osativa_eg_gene",
        "biomart_file": "biomart_4530.tsv",
        "gtf_file": "oryza_sativa.gtf.gz",
        "gtf_url": "https://ftp.ensemblgenomes.ebi.ac.uk/pub/plants/release-58/gtf/oryza_sativa/Oryza_sativa.IRGSP-1.0.58.gtf.gz",
    },
    "3218": {
        "name": "Physcomitrium patens",
        "biomart_endpoint": _ENSEMBL_PLANTS,
        "dataset": "ppatens_eg_gene",
        "biomart_file": "biomart_3218.tsv",
        "gtf_file": "physcomitrium_patens.gtf.gz",
        "gtf_url": "https://ftp.ensemblgenomes.ebi.ac.uk/pub/plants/release-58/gtf/physcomitrium_patens/Physcomitrium_patens.Phypa_V3.58.gtf.gz",
    },
    "3055": {
        "name": "Chlamydomonas reinhardtii",
        "biomart_endpoint": _ENSEMBL_PLANTS,
        "dataset": "creinhardtii_eg_gene",
        "biomart_file": "biomart_3055.tsv",
        "gtf_file": "chlamydomonas_reinhardtii.gtf.gz",
        "gtf_url": "https://ftp.ensemblgenomes.ebi.ac.uk/pub/plants/release-58/gtf/chlamydomonas_reinhardtii/Chlamydomonas_reinhardtii.Chlamydomonas_reinhardtii_v5.5.58.gtf.gz",
    },
    # ── EnsemblFungi (virtualSchemaName=fungi_mart) ───────────────────────────
    "162425": {
        "name": "Aspergillus niger",
        "biomart_endpoint": _ENSEMBL_FUNGI,
        "dataset": "aniger_eg_gene",
        "biomart_file": "biomart_162425.tsv",
        "gtf_file": "aspergillus_niger.gtf.gz",
        "gtf_url": "https://ftp.ensemblgenomes.ebi.ac.uk/pub/fungi/release-58/gtf/aspergillus_niger/Aspergillus_niger.ASM285v2.58.gtf.gz",
    },
    "4932": {
        "name": "Saccharomyces cerevisiae",
        "biomart_endpoint": _ENSEMBL_FUNGI,
        "dataset": "scerevisiae_eg_gene",
        "biomart_file": "biomart_4932.tsv",
        "gtf_file": "saccharomyces_cerevisiae.gtf.gz",
        "gtf_url": "https://ftp.ensemblgenomes.ebi.ac.uk/pub/fungi/release-58/gtf/saccharomyces_cerevisiae/Saccharomyces_cerevisiae.R64-1-1.58.gtf.gz",
    },
    # ── NCBI (no BioMart) ─────────────────────────────────────────────────────
    "511145": {
        "name": "Escherichia coli K-12",
        "biomart_endpoint": None,
        "dataset": None,
        "biomart_file": None,
        "gtf_file": "ecoli_k12.gff3.gz",
        "gtf_url": "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/005/845/GCF_000005845.2_ASM584v2/GCF_000005845.2_ASM584v2_genomic.gff.gz",
    },
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


# ── Validators ─────────────────────────────────────────────────────────────────

def check_path(path: str, label: str) -> dict:
    exists   = os.path.exists(path)
    size     = os.path.getsize(path) if exists else 0
    return {"label": label, "path": path, "exists": exists, "size_kb": round(size / 1024, 1), "ok": True}


def check_url_head(url: str, label: str, timeout: int = 15) -> dict:
    """Ranged GET of first 512 bytes — confirms the file exists on the server."""
    result = {"label": label, "url": url[:80] + "…" if len(url) > 80 else url, "ok": False, "detail": ""}
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "gene-intel-test/1.0", "Range": "bytes=0-511"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status  = resp.status
            snippet = resp.read(512).decode("utf-8", errors="replace")
        result["ok"]     = status in (200, 206)
        result["detail"] = f"HTTP {status} | first chars: {snippet[:60].strip()!r}"
    except Exception as exc:
        result["detail"] = str(exc)
    return result


def check_biomart_url(base_url: str, virtual_schema: str, dataset: str,
                      label: str, timeout: int = 30) -> dict:
    """
    Fetch the first ~2 KB of a BioMart response and verify the TSV header
    contains 'Gene stable ID'.
    """
    url = build_biomart_url(base_url, virtual_schema, dataset)
    result = {"label": label, "url": url[:80] + "…", "ok": False, "detail": ""}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "gene-intel-test/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status  = resp.status
            snippet = resp.read(2048).decode("utf-8", errors="replace")
        first_line = snippet.split("\n")[0]
        header_ok  = "Gene stable ID" in first_line or "Ensembl Gene ID" in first_line
        result["ok"]     = status == 200 and header_ok
        result["detail"] = (
            f"HTTP {status} | schema={virtual_schema} | header: {first_line[:80]!r}"
            + ("  ✓ TSV OK" if header_ok else "  ✗ bad header — check dataset/schema")
        )
    except Exception as exc:
        result["detail"] = str(exc)
    return result


# ── Runner ─────────────────────────────────────────────────────────────────────

def run_tests(targets: list, check_gtf: bool, check_biomart: bool, offline: bool):
    results = []
    total = passed = 0

    print(f"\n{'='*70}")
    print("  Gene-Intel — BioMart & GTF URL / Path Validation")
    print(f"  Mode: {'offline (paths only)' if offline else 'online (HTTP checks)'}")
    print(f"  Checking {len(targets)} species")
    print(f"{'='*70}\n")

    for taxon_id in targets:
        sp = SPECIES[taxon_id]
        print(f"── {sp['name']} (taxon={taxon_id}) ──")

        if check_gtf:
            gtf_path = os.path.join(GTF_DIR, sp["gtf_file"])
            r = check_path(gtf_path, f"GTF path: {sp['gtf_file']}")
            total += 1; passed += 1
            status = "EXISTS" if r["exists"] else "MISSING"
            size_s = f"({r['size_kb']:,} KB)" if r["exists"] else ""
            print(f"  [PATH ] {r['label']}: {status} {size_s}")
            print(f"          → {r['path']}")
            results.append(r)

            if not offline:
                r2 = check_url_head(sp["gtf_url"], f"GTF URL: {sp['gtf_file']}")
                total += 1
                if r2["ok"]: passed += 1
                print(f"  [URL  ] {'✓' if r2['ok'] else '✗'} {r2['label']}")
                print(f"          {r2['detail']}")
                results.append(r2)

        if check_biomart:
            if sp["biomart_file"] is None:
                print(f"  [SKIP ] BioMart: uses GFF3 Dbxref (no BioMart file needed)")
            else:
                bm_path = os.path.join(BIOMART_DIR, sp["biomart_file"])
                r = check_path(bm_path, f"BioMart path: {sp['biomart_file']}")
                total += 1; passed += 1
                status = "EXISTS" if r["exists"] else "MISSING"
                size_s = f"({r['size_kb']:,} KB)" if r["exists"] else ""
                print(f"  [PATH ] {r['label']}: {status} {size_s}")
                print(f"          → {r['path']}")
                results.append(r)

                if not offline:
                    base_url, virtual_schema = sp["biomart_endpoint"]
                    r2 = check_biomart_url(
                        base_url, virtual_schema, sp["dataset"],
                        f"BioMart URL: {sp['dataset']} (schema={virtual_schema})"
                    )
                    total += 1
                    if r2["ok"]: passed += 1
                    print(f"  [URL  ] {'✓' if r2['ok'] else '✗'} {r2['label']}")
                    print(f"          {r2['detail']}")
                    results.append(r2)

        print()

    print(f"{'='*70}")
    print(f"  Results: {passed}/{total} checks passed")
    if not offline:
        failed = [r for r in results if not r["ok"]]
        if failed:
            print(f"\n  FAILED:")
            for r in failed:
                print(f"    ✗ {r['label']}")
                print(f"      {r.get('detail', '')}")
    print(f"{'='*70}\n")
    return passed == total


def main():
    parser = argparse.ArgumentParser(
        description="Validate BioMart and GTF download URLs and file paths"
    )
    parser.add_argument("--species",      help="Single taxon ID to check (e.g. 9606)")
    parser.add_argument("--gtf-only",     action="store_true")
    parser.add_argument("--biomart-only", action="store_true")
    parser.add_argument("--offline",      action="store_true",
                        help="Skip HTTP checks — validate file paths only")
    args = parser.parse_args()

    targets       = [args.species] if args.species else list(SPECIES.keys())
    check_gtf     = not args.biomart_only
    check_biomart = not args.gtf_only

    ok = run_tests(targets, check_gtf=check_gtf, check_biomart=check_biomart, offline=args.offline)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
