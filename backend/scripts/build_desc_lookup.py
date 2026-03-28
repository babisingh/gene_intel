#!/usr/bin/env python3
"""
One-time script to build backend/app/db/domain_desc_lookup.json.gz

Downloads:
  1. Pfam-A.hmm.dat.gz  — Stockholm metadata file; parse #=GF AC and #=GF DE
  2. interpro/entry.list — TSV of all InterPro entries (IPR accession + name)
  3. go-basic.obo        — OBO flat-file; parse [Term] id: / name: blocks

Produces backend/app/db/domain_desc_lookup.json.gz with schema:
  {
    "pfam":     {"PF00001": "...", ...},    # ~20K entries
    "interpro": {"IPR000001": "...", ...},  # ~45K entries
    "go":       {"GO:0000001": "...", ...}, # ~47K entries
  }

Re-run this script whenever Pfam / GO release new versions (quarterly / monthly).
"""

import gzip
import json
import re
import sys
import urllib.request
from pathlib import Path

OUT = Path(__file__).parent.parent / "app" / "db" / "domain_desc_lookup.json.gz"

PFAM_URL    = "https://ftp.ebi.ac.uk/pub/databases/Pfam/current_release/Pfam-A.hmm.dat.gz"
INTERPRO_URL = "https://ftp.ebi.ac.uk/pub/databases/interpro/current_release/entry.list"
GO_URL      = "https://purl.obolibrary.org/obo/go/go-basic.obo"


def download(url: str, label: str) -> bytes:
    print(f"  Downloading {label} … ", end="", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Gene-Intel/2.0 build-script"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    print(f"{len(data) // 1024} KB")
    return data


# ── Pfam ─────────────────────────────────────────────────────────────────────

def parse_pfam(raw_gz: bytes) -> dict[str, str]:
    """
    Parse Pfam-A.hmm.dat.gz (Stockholm format).
    Each family is a block separated by '//'.
    We extract #=GF AC (accession, strip version) and #=GF DE (description).
    """
    result: dict[str, str] = {}
    acc = desc = None
    # Stream-decompress in chunks to avoid loading all into memory
    text = gzip.decompress(raw_gz).decode("utf-8", errors="replace")
    for line in text.splitlines():
        if line.startswith("#=GF AC"):
            raw_acc = line.split(None, 2)[2].strip()
            acc = raw_acc.split(".")[0]   # strip version suffix e.g. PF00001.24 → PF00001
        elif line.startswith("#=GF DE"):
            desc = line.split(None, 2)[2].strip()
        elif line == "//":
            if acc and desc:
                result[acc] = desc
            acc = desc = None
    return result


# ── InterPro entry list ───────────────────────────────────────────────────────

def parse_interpro(raw: bytes) -> dict[str, str]:
    """
    Parse entry.list TSV: ENTRY_AC  ENTRY_TYPE  ENTRY_NAME
    Covers all InterPro families (IPR…).
    """
    result: dict[str, str] = {}
    for line in raw.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("ENTRY_AC"):
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            acc  = parts[0].strip()
            name = parts[2].strip()
            if acc.startswith("IPR") and name:
                result[acc] = name
    return result


# ── GO OBO ───────────────────────────────────────────────────────────────────

def parse_go_obo(raw: bytes) -> dict[str, str]:
    """
    Parse go-basic.obo flat file.
    Collect id: / name: pairs from [Term] blocks.
    """
    result: dict[str, str] = {}
    in_term = False
    term_id = term_name = None
    for line in raw.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if line == "[Term]":
            in_term = True
            term_id = term_name = None
        elif line.startswith("[") and line.endswith("]"):
            in_term = False
        elif in_term:
            if line.startswith("id:"):
                term_id = line[3:].strip()
            elif line.startswith("name:"):
                term_name = line[5:].strip()
            elif line == "":
                if term_id and term_name and term_id.startswith("GO:"):
                    result[term_id] = term_name
                term_id = term_name = None
    # flush last term
    if term_id and term_name and term_id.startswith("GO:"):
        result[term_id] = term_name
    return result


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("Building domain_desc_lookup.json.gz …")

    pfam_raw      = download(PFAM_URL,      "Pfam-A.hmm.dat.gz")
    interpro_raw  = download(INTERPRO_URL,  "InterPro entry.list")
    go_raw        = download(GO_URL,        "go-basic.obo")

    print("  Parsing Pfam … ", end="", flush=True)
    pfam = parse_pfam(pfam_raw)
    print(f"{len(pfam):,} entries")

    print("  Parsing InterPro … ", end="", flush=True)
    interpro = parse_interpro(interpro_raw)
    print(f"{len(interpro):,} entries")

    print("  Parsing GO … ", end="", flush=True)
    go = parse_go_obo(go_raw)
    print(f"{len(go):,} entries")

    payload = {"pfam": pfam, "interpro": interpro, "go": go}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    raw_json = json.dumps(payload, separators=(",", ":")).encode()
    with gzip.open(OUT, "wb", compresslevel=9) as f:
        f.write(raw_json)

    size_kb = OUT.stat().st_size // 1024
    print(f"\n✓ Written to {OUT}  ({size_kb} KB compressed)")
    print(f"  Pfam: {len(pfam):,}  InterPro: {len(interpro):,}  GO: {len(go):,}")


if __name__ == "__main__":
    main()
