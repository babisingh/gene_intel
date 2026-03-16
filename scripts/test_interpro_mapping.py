#!/usr/bin/env python3
"""
Proof-of-concept: map Ensembl gene IDs to InterPro/Pfam domains via:
  1. UniProt per-organism idmapping.dat.gz  (UniProt acc → Ensembl gene ID)
  2. UniProt REST API                       (UniProt acc → InterPro / Pfam xrefs)

Test species: S. cerevisiae (taxon 4932 / UniProt code YEAST_559292)

Output: same {gene_id, domain_id, source, description} shape as biomart_parser.py

Run from repo root:
    python scripts/test_interpro_mapping.py
"""

import gzip
import json
import os
import sys
import time
import urllib.request
import urllib.parse
from collections import defaultdict

TAXON_ID       = "4932"
UNIPROT_CODE   = "YEAST_559292"
IDMAP_DIR      = "./data/interpro"
IDMAP_FILE     = os.path.join(IDMAP_DIR, f"{UNIPROT_CODE}_idmapping.dat.gz")
IDMAP_URL      = (
    "https://ftp.uniprot.org/pub/databases/uniprot/current_release/"
    f"knowledgebase/idmapping/by_organism/{UNIPROT_CODE}_idmapping.dat.gz"
)

UNIPROT_API    = "https://rest.uniprot.org/uniprotkb/search"
BATCH_SIZE     = 50    # search endpoint: keep URL short (~1KB per batch)
FIELDS         = "accession,xref_interpro,xref_pfam"


# ── Step 1: Download idmapping file if needed ─────────────────────────────────

def ensure_idmap():
    os.makedirs(IDMAP_DIR, exist_ok=True)
    if os.path.exists(IDMAP_FILE) and os.path.getsize(IDMAP_FILE) > 0:
        print(f"[1] idmapping already present: {IDMAP_FILE}")
        return
    print(f"[1] Downloading {IDMAP_FILE} …")
    req = urllib.request.Request(IDMAP_URL, headers={"User-Agent": "gene-intel/1.0"})
    with urllib.request.urlopen(req) as resp, open(IDMAP_FILE, "wb") as f:
        while chunk := resp.read(256 * 1024):
            f.write(chunk)
    print(f"    saved {os.path.getsize(IDMAP_FILE):,} bytes")


# ── Step 2: Parse idmapping → uniprot_acc → ensembl_gene_id ─────────────────

def build_uniprot_to_gene(idmap_path: str) -> dict:
    """Returns {uniprot_acc: ensembl_gene_id}"""
    mapping = {}
    with gzip.open(idmap_path, "rt") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 3:
                continue
            acc, id_type, value = parts
            if id_type == "EnsemblGenome":
                mapping[acc] = value
    print(f"[2] UniProt→Gene map: {len(mapping):,} entries")
    return mapping


# ── Step 3: Batch-query UniProt REST for InterPro/Pfam xrefs ─────────────────

def _query_batch(accessions: list) -> list:
    """
    Returns list of dicts: {accession, interpro: [...], pfam: [...]}
    Uses UniProt GET /uniprotkb/search with OR-joined accession query.
    Batch size kept at 50 to avoid URL length limits.
    """
    query = " OR ".join(f"accession:{a}" for a in accessions)
    params = urllib.parse.urlencode({
        "query":  query,
        "fields": FIELDS,
        "format": "tsv",
        "size":   len(accessions),
    })
    url = f"{UNIPROT_API}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "gene-intel/1.0"})

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8")
            break
        except Exception as exc:
            if attempt == 2:
                raise
            wait = 2 ** attempt
            print(f"    retry {attempt+1} after {wait}s ({exc})")
            time.sleep(wait)

    rows = raw.strip().split("\n")
    if not rows or len(rows) < 2:
        return []

    header = rows[0].split("\t")
    results = []
    for row in rows[1:]:
        cols = row.split("\t")
        if len(cols) < len(header):
            continue
        rec = dict(zip(header, cols))
        acc = rec.get("Entry", "").strip()
        interpro_raw = rec.get("InterPro", "").strip()
        pfam_raw     = rec.get("Pfam", "").strip()
        results.append({
            "accession": acc,
            "interpro":  [x.strip() for x in interpro_raw.split(";") if x.strip()],
            "pfam":      [x.strip() for x in pfam_raw.split(";")      if x.strip()],
        })
    return results


def fetch_domains(accessions: list) -> dict:
    """
    Returns {uniprot_acc: {interpro: [...], pfam: [...]}}
    """
    all_batches = [accessions[i:i+BATCH_SIZE] for i in range(0, len(accessions), BATCH_SIZE)]
    result = {}
    print(f"[3] Querying UniProt REST API: {len(accessions):,} accessions "
          f"in {len(all_batches)} batches of {BATCH_SIZE} …")

    for i, batch in enumerate(all_batches, 1):
        rows = _query_batch(batch)
        for r in rows:
            result[r["accession"]] = {
                "interpro": r["interpro"],
                "pfam":     r["pfam"],
            }
        print(f"    batch {i}/{len(all_batches)}: {len(rows)} records", end="\r")
        if i < len(all_batches):
            time.sleep(0.3)   # polite rate limiting

    print(f"\n    total fetched: {len(result):,} proteins with domain data")
    return result


# ── Step 4: Build gene→domain association list ────────────────────────────────

def build_domain_associations(uniprot_to_gene: dict, domain_data: dict) -> list:
    """
    Returns list of {gene_id, domain_id, source, description}
    — same shape as biomart_parser.parse_biomart_tsv()
    """
    results = []
    for acc, domains in domain_data.items():
        gene_id = uniprot_to_gene.get(acc)
        if not gene_id:
            continue
        for ipr_id in domains["interpro"]:
            results.append({
                "gene_id":     gene_id,
                "domain_id":   f"InterPro:{ipr_id}",
                "source":      "InterPro",
                "description": "",
            })
        for pfam_id in domains["pfam"]:
            results.append({
                "gene_id":     gene_id,
                "domain_id":   f"Pfam:{pfam_id}",
                "source":      "Pfam",
                "description": "",
            })
    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ensure_idmap()
    uniprot_to_gene = build_uniprot_to_gene(IDMAP_FILE)
    accessions = list(uniprot_to_gene.keys())

    domain_data = fetch_domains(accessions)

    associations = build_domain_associations(uniprot_to_gene, domain_data)

    print(f"\n[4] Domain associations built: {len(associations):,}")

    # Compare with existing BioMart yeast file
    biomart_path = "./data/biomart/biomart_4932.tsv"
    if os.path.exists(biomart_path):
        import csv
        bm_genes, bm_domains = set(), set()
        PFAM_COLS  = {"Pfam domain", "Pfam domain ID", "Pfam ID"}
        IPR_COLS   = {"InterPro accession", "InterPro ID", "Interpro ID"}
        with open(biomart_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            pfam_col = next((c for c in (reader.fieldnames or []) if c in PFAM_COLS), None)
            ipr_col  = next((c for c in (reader.fieldnames or []) if c in IPR_COLS),  None)
            for row in reader:
                g = row.get("Gene stable ID", row.get("Ensembl Gene ID", "")).strip()
                if not g:
                    continue
                bm_genes.add(g)
                p   = row.get(pfam_col, "").strip() if pfam_col else ""
                ipr = row.get(ipr_col,  "").strip() if ipr_col  else ""
                if p:
                    bm_domains.add((g, f"Pfam:{p}"))
                if ipr:
                    bm_domains.add((g, f"InterPro:{ipr}"))

        new_genes   = {a["gene_id"] for a in associations}
        new_domains = {(a["gene_id"], a["domain_id"]) for a in associations}

        print(f"\n--- Comparison with BioMart yeast file ---")
        print(f"  BioMart genes:         {len(bm_genes):>6,}")
        print(f"  InterPro-FTP genes:    {len(new_genes):>6,}")
        print(f"  BioMart associations:  {len(bm_domains):>6,}")
        print(f"  InterPro-FTP assocs:   {len(new_domains):>6,}")
        overlap = bm_domains & new_domains
        print(f"  Overlap:               {len(overlap):>6,}")
        only_bm  = bm_domains - new_domains
        only_new = new_domains - bm_domains
        print(f"  Only in BioMart:       {len(only_bm):>6,}")
        print(f"  Only in InterPro-FTP:  {len(only_new):>6,}")

    # Print a sample
    print("\n--- Sample associations (first 10) ---")
    for a in associations[:10]:
        print(f"  {a['gene_id']:<12}  {a['domain_id']}")

    print("\nDone.")


if __name__ == "__main__":
    main()
