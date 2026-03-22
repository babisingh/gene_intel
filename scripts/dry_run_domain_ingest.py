#!/usr/bin/env python3
"""
Dry run for UniProt domain ingestion (no Neo4j required).

Fetches 2 pages of UniProt domain data for human and validates the schema
of returned records. Does NOT write to Neo4j.

Usage:
    python scripts/dry_run_domain_ingest.py
"""

import sys
import os
import json
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
logger = logging.getLogger(__name__)

REQUIRED_KEYS = {"uniprot_acc", "gene_name", "pfam_acc", "domain_name",
                 "start_aa", "end_aa", "e_value", "domain_id", "source_db"}

REQUIRED_TYPES = {
    "uniprot_acc": str,
    "gene_name": str,
    "pfam_acc": str,
    "domain_name": str,
    "start_aa": int,
    "end_aa": int,
    "domain_id": str,
    "source_db": str,
}


def validate_domain(d: dict, idx: int) -> list[str]:
    """Return list of validation errors for a domain dict."""
    errors = []
    missing = REQUIRED_KEYS - set(d.keys())
    if missing:
        errors.append(f"Record {idx}: missing keys {missing}")
        return errors

    for key, expected_type in REQUIRED_TYPES.items():
        if d[key] is not None and not isinstance(d[key], expected_type):
            errors.append(
                f"Record {idx}: {key} is {type(d[key]).__name__}, expected {expected_type.__name__}"
            )

    if d["pfam_acc"] and not d["pfam_acc"].startswith("PF"):
        errors.append(f"Record {idx}: pfam_acc '{d['pfam_acc']}' doesn't start with 'PF'")

    if d["start_aa"] is not None and d["end_aa"] is not None:
        if d["start_aa"] >= d["end_aa"]:
            errors.append(f"Record {idx}: start_aa ({d['start_aa']}) >= end_aa ({d['end_aa']})")

    return errors


def main():
    from app.ingestion.domain_ingest_uniprot import fetch_uniprot_domains

    print("=" * 60)
    print("Gene-Intel Domain Ingest — Dry Run")
    print("=" * 60)
    print("Fetching UniProt domains for taxon 9606 (max 2 pages)...")
    print("")

    try:
        domains = fetch_uniprot_domains(taxon_id=9606, reviewed_only=True, max_pages=2)
    except Exception as exc:
        print(f"ERROR fetching domains: {exc}")
        sys.exit(1)

    print(f"Total domains extracted: {len(domains):,}")
    print("")

    # Show sample records
    print("Sample domain records:")
    for d in domains[:5]:
        print(json.dumps(d, indent=2, default=str))
        print("")

    # Validate all records
    all_errors = []
    for i, d in enumerate(domains):
        errs = validate_domain(d, i)
        all_errors.extend(errs)

    valid_count = len(domains) - len(all_errors)
    if all_errors:
        print(f"Schema validation: {valid_count}/{len(domains)} records valid")
        print("\nValidation errors:")
        for err in all_errors[:10]:
            print(f"  - {err}")
        if len(all_errors) > 10:
            print(f"  ... and {len(all_errors) - 10} more errors")
        sys.exit(1)
    else:
        print(f"Schema validation: {len(domains)}/{len(domains)} records valid ✓")
        sys.exit(0)


if __name__ == "__main__":
    main()
