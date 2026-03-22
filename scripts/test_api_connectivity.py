#!/usr/bin/env python3
"""
Gene-Intel API Connectivity Test Suite.

Tests all 5 domain data sources before any ingestion code is run.
Each test is independent — one failure does not stop the others.

Usage:
    python scripts/test_api_connectivity.py

Exit code: 0 if all PASS or WARN, 1 if any FAIL.
"""

import sys
import time
import json
import os

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "--quiet"])
    import requests


TIMEOUT = 20
INTERPROSCAN_TIMEOUT = 30
SLEEP_BETWEEN_TESTS = 5

results = []  # list of (name, status, notes, elapsed)


def _status_line(name, status, notes, elapsed):
    status_str = {
        "PASS": "PASS",
        "FAIL": "FAIL",
        "WARN": "WARN",
    }[status]
    print(f"  [{status_str}] {name}: {notes} ({elapsed:.1f}s)")
    results.append((name, status, notes, elapsed))


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1 — InterPro REST API
# ─────────────────────────────────────────────────────────────────────────────

def test_interpro_rest():
    print("\n── TEST 1: InterPro REST API ─────────────────────────────────────────────")
    t0 = time.monotonic()
    try:
        url = "https://www.ebi.ac.uk/interpro/api/entry/pfam/protein/uniprot"
        params = {"taxonomy_id": 9606, "page_size": 5}
        headers = {"Accept": "application/json"}
        resp = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
        elapsed = time.monotonic() - t0

        if resp.status_code != 200:
            print(f"  Response body (first 300 chars): {resp.text[:300]}")
            _status_line("InterPro REST", "FAIL", f"HTTP {resp.status_code}", elapsed)
            return

        data = resp.json()
        required_keys = {"count", "next", "results"}
        missing = required_keys - set(data.keys())
        if missing:
            _status_line("InterPro REST", "FAIL", f"Missing JSON keys: {missing}", elapsed)
            return

        if not data["results"]:
            _status_line("InterPro REST", "WARN", "results list is empty", elapsed)
            return

        first = data["results"][0]
        accession = first.get("metadata", {}).get("accession", "")
        source_db = first.get("metadata", {}).get("source_database", "")

        if not accession.startswith("PF"):
            _status_line("InterPro REST", "WARN",
                         f"First accession doesn't start with PF: {accession}", elapsed)
            return

        if source_db != "pfam":
            _status_line("InterPro REST", "WARN",
                         f"source_database is '{source_db}', expected 'pfam'", elapsed)
            return

        count = data["count"]
        _status_line("InterPro REST", "PASS",
                     f"{count:,} Pfam entries for human", elapsed)

    except requests.exceptions.Timeout:
        elapsed = time.monotonic() - t0
        _status_line("InterPro REST", "FAIL", f"Timeout after {TIMEOUT}s", elapsed)
    except Exception as exc:
        elapsed = time.monotonic() - t0
        _status_line("InterPro REST", "FAIL", str(exc), elapsed)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2 — UniProt REST API
# ─────────────────────────────────────────────────────────────────────────────

def test_uniprot_rest():
    print("\n── TEST 2: UniProt REST API ──────────────────────────────────────────────")
    t0 = time.monotonic()
    try:
        url = "https://rest.uniprot.org/uniprotkb/search"
        params = {
            "query": "(taxonomy_id:9606 AND reviewed:true)",
            "fields": "accession,gene_names,ft_domain",
            "format": "json",
            "size": 5,
        }
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        elapsed = time.monotonic() - t0

        if resp.status_code != 200:
            _status_line("UniProt REST", "FAIL", f"HTTP {resp.status_code}: {resp.text[:200]}", elapsed)
            return

        data = resp.json()
        if "results" not in data:
            _status_line("UniProt REST", "FAIL", "Missing 'results' key in response", elapsed)
            return

        if len(data["results"]) < 1:
            _status_line("UniProt REST", "FAIL", "No results returned", elapsed)
            return

        first = data["results"][0]
        if "features" not in first:
            _status_line("UniProt REST", "WARN",
                         "results[0] has no 'features' key (may be empty for some proteins)", elapsed)
            # This is OK per spec — features may be empty
        else:
            pass  # features exists

        total_hits = resp.headers.get("X-Total-Results", "unknown")
        _status_line("UniProt REST", "PASS",
                     f"{total_hits} reviewed human proteins", elapsed)

    except requests.exceptions.Timeout:
        elapsed = time.monotonic() - t0
        _status_line("UniProt REST", "FAIL", f"Timeout after {TIMEOUT}s", elapsed)
    except Exception as exc:
        elapsed = time.monotonic() - t0
        _status_line("UniProt REST", "FAIL", str(exc), elapsed)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3 — EMBL-EBI FTP
# ─────────────────────────────────────────────────────────────────────────────

def _parse_ftp_filesize(html, filename):
    """Parse file size from FTP HTML directory listing."""
    import re
    # Apache-style: <filename>   YYYY-MM-DD HH:MM   SIZE
    # Try to find the size next to the filename
    pattern = re.compile(
        r'href="[^"]*' + re.escape(filename) + r'"[^>]*>[^<]*</a>\s+[\d-]+\s+[\d:]+\s+([\d\.]+[KMGT]?)',
        re.IGNORECASE,
    )
    m = pattern.search(html)
    if m:
        return m.group(1)

    # Alternative: just find any number-like size after filename mention
    lines = html.split("\n")
    for line in lines:
        if filename in line:
            # Look for a size-like token (digits, possibly followed by unit)
            tokens = line.split()
            for tok in reversed(tokens):
                if re.match(r'^\d+[\.,]?\d*[KMGT]?$', tok, re.IGNORECASE):
                    return tok
    return "unknown"


def test_embl_ftp():
    print("\n── TEST 3: EMBL-EBI FTP ──────────────────────────────────────────────────")
    t0 = time.monotonic()
    try:
        url = "https://ftp.ebi.ac.uk/pub/databases/interpro/current_release/"
        resp = requests.get(url, timeout=TIMEOUT)
        elapsed = time.monotonic() - t0

        if resp.status_code != 200:
            _status_line("EMBL-EBI FTP", "FAIL", f"HTTP {resp.status_code}", elapsed)
            return

        body = resp.text
        has_match_complete = "match_complete.xml.gz" in body
        has_protein2ipr = "protein2ipr.dat.gz" in body

        if not has_match_complete or not has_protein2ipr:
            missing = []
            if not has_match_complete:
                missing.append("match_complete.xml.gz")
            if not has_protein2ipr:
                missing.append("protein2ipr.dat.gz")
            _status_line("EMBL-EBI FTP", "FAIL",
                         f"Missing files in listing: {', '.join(missing)}", elapsed)
            return

        size_match = _parse_ftp_filesize(body, "match_complete.xml.gz")
        size_protein = _parse_ftp_filesize(body, "protein2ipr.dat.gz")
        _status_line("EMBL-EBI FTP", "PASS",
                     f"match_complete.xml.gz={size_match}, protein2ipr.dat.gz={size_protein}", elapsed)

    except requests.exceptions.Timeout:
        elapsed = time.monotonic() - t0
        _status_line("EMBL-EBI FTP", "FAIL", f"Timeout after {TIMEOUT}s", elapsed)
    except Exception as exc:
        elapsed = time.monotonic() - t0
        _status_line("EMBL-EBI FTP", "FAIL", str(exc), elapsed)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 4 — InterProScan REST web service
# ─────────────────────────────────────────────────────────────────────────────

def test_interproscan_rest():
    print("\n── TEST 4: InterProScan REST web service ────────────────────────────────")
    t0 = time.monotonic()
    try:
        url = "https://www.ebi.ac.uk/Tools/services/rest/iprscan5/run"
        data = {
            "email": "test@example.com",
            "title": "gene_intel_connectivity_test",
            "goterms": "false",
            "pathways": "false",
            "sequence": "MTEYKLVVVGAGGVGKSALTIQLIQNHFVDEYDPTIEDSY",
        }
        resp = requests.post(url, data=data, timeout=INTERPROSCAN_TIMEOUT)
        elapsed = time.monotonic() - t0

        if resp.status_code != 200:
            _status_line("InterProScan REST", "FAIL",
                         f"HTTP {resp.status_code}: {resp.text[:300]}", elapsed)
            return

        job_id = resp.text.strip()

        if not job_id or "ERROR" in job_id.upper():
            _status_line("InterProScan REST", "FAIL",
                         f"Response doesn't look like a job ID: {job_id[:100]}", elapsed)
            return

        # Save job ID to file for optional later inspection
        try:
            with open(".iprscan_test_jobid", "w") as f:
                f.write(job_id)
        except OSError:
            pass  # Non-fatal if we can't write

        _status_line("InterProScan REST", "PASS",
                     f"Job ID: {job_id}", elapsed)

    except requests.exceptions.Timeout:
        elapsed = time.monotonic() - t0
        _status_line("InterProScan REST", "FAIL",
                     f"Timeout after {INTERPROSCAN_TIMEOUT}s", elapsed)
    except Exception as exc:
        elapsed = time.monotonic() - t0
        _status_line("InterProScan REST", "FAIL", str(exc), elapsed)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 5 — Ensembl REST API
# ─────────────────────────────────────────────────────────────────────────────

def test_ensembl_rest():
    print("\n── TEST 5: Ensembl REST API ──────────────────────────────────────────────")
    t0 = time.monotonic()
    try:
        url = "https://rest.ensembl.org/info/species"
        params = {"content-type": "application/json"}
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        elapsed = time.monotonic() - t0

        if resp.status_code != 200:
            _status_line("Ensembl REST", "FAIL", f"HTTP {resp.status_code}", elapsed)
            return

        data = resp.json()
        if "species" not in data:
            _status_line("Ensembl REST", "FAIL", "Missing 'species' key in response", elapsed)
            return

        count = len(data["species"])
        if count < 200:
            _status_line("Ensembl REST", "WARN",
                         f"Only {count} species (expected >= 200)", elapsed)
            return

        _status_line("Ensembl REST", "PASS", f"{count} species available", elapsed)

    except requests.exceptions.Timeout:
        elapsed = time.monotonic() - t0
        _status_line("Ensembl REST", "FAIL", f"Timeout after {TIMEOUT}s", elapsed)
    except Exception as exc:
        elapsed = time.monotonic() - t0
        _status_line("Ensembl REST", "FAIL", str(exc), elapsed)


# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def print_summary():
    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print(f"  {'API Source':<22} | {'Status':<6} | Notes")
    print(f"  {'-'*22}-+-{'-'*6}-+-{'-'*36}")
    any_fail = False
    for name, status, notes, elapsed in results:
        if status == "FAIL":
            any_fail = True
        print(f"  {name:<22} | {status:<6} | {notes}")
    print("=" * 72)
    return any_fail


def main():
    print("Gene-Intel API Connectivity Test Suite")
    print("=" * 72)
    print("Testing all 5 data sources... (5-second pause between each)")

    tests = [
        ("InterPro REST", test_interpro_rest),
        ("UniProt REST", test_uniprot_rest),
        ("EMBL-EBI FTP", test_embl_ftp),
        ("InterProScan REST", test_interproscan_rest),
        ("Ensembl REST", test_ensembl_rest),
    ]

    for i, (name, fn) in enumerate(tests):
        fn()
        if i < len(tests) - 1:
            print(f"\n  (sleeping {SLEEP_BETWEEN_TESTS}s to avoid rate limiting...)")
            time.sleep(SLEEP_BETWEEN_TESTS)

    any_fail = print_summary()
    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()
