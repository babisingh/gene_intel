#!/usr/bin/env python3
"""
Standalone entry point for FTP bulk domain ingestion.

Downloads and parses protein2ipr.dat.gz from InterPro FTP and loads
domain annotations for all 17 Gene-Intel species into Neo4j.

Prerequisites:
  1. Download the FTP file first:
       bash scripts/download_interpro_ftp.sh
  2. GTF data must be loaded (gene nodes must exist in Neo4j)

Usage:
  python scripts/ingest_domains_ftp.py --ftp-file data/interpro_ftp/protein2ipr.dat.gz
  python scripts/ingest_domains_ftp.py --ftp-file <path> --taxons 9606 10090 7955
"""

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.db.neo4j_client import get_driver, verify_connectivity, close_driver
from app.ingestion.domain_ingest_ftp import run_ftp_domain_ingest
from app.ingestion.run_ingest import SPECIES_REGISTRY

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s — %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Gene-Intel FTP bulk domain ingestion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Ingest all 17 species
  python scripts/ingest_domains_ftp.py --ftp-file data/interpro_ftp/protein2ipr.dat.gz

  # Ingest specific species only
  python scripts/ingest_domains_ftp.py --ftp-file <path> --taxons 9606 10090
        """,
    )
    parser.add_argument(
        "--ftp-file", required=True,
        help="Path to downloaded protein2ipr.dat.gz",
    )
    parser.add_argument(
        "--taxons", nargs="*", type=int, default=None,
        help="Taxon IDs to process (default: all 17 species)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.ftp_file):
        logger.error("FTP file not found: %s", args.ftp_file)
        logger.error("Download with: bash scripts/download_interpro_ftp.sh")
        sys.exit(1)

    if not verify_connectivity():
        logger.error("Cannot connect to Neo4j. Check .env file.")
        sys.exit(1)

    taxon_ids = args.taxons or [int(t) for t in SPECIES_REGISTRY.keys()]
    logger.info("Processing %d species: %s", len(taxon_ids), taxon_ids)

    driver = get_driver()
    try:
        stats = run_ftp_domain_ingest(args.ftp_file, driver, taxon_ids)
        logger.info("Done! Total domains loaded: %d", stats["total_loaded"])
        logger.info("Per-species breakdown: %s", stats.get("per_taxon", {}))
    finally:
        close_driver()


if __name__ == "__main__":
    main()
