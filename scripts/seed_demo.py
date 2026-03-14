#!/usr/bin/env python3
"""
Quick demo seed: Human (9606) + Zebrafish (7955) only.

Loads two species for a fast demo — typically completes in ~5 minutes
compared to ~2 hours for all 15 species.

Prerequisites:
  1. GTF files downloaded:
       bash scripts/download_ensembl.sh
  2. BioMart TSVs downloaded (for domain annotations)
  3. Neo4j schema initialised:
       python scripts/init_schema.py

Usage:
    python scripts/seed_demo.py
"""

import sys
import os
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.db.neo4j_client import get_driver, verify_connectivity, close_driver
from app.db.schema import init_schema
from app.ingestion.run_ingest import ingest_species

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s — %(message)s",
)
logger = logging.getLogger(__name__)

DEMO_SPECIES = ["9606", "7955"]  # Human + Zebrafish


def main():
    logger.info("Gene-Intel Demo Seed")
    logger.info("Species: Human (9606) + Zebrafish (7955)")
    logger.info("")

    if not verify_connectivity():
        logger.error("Cannot connect to Neo4j. Check .env file.")
        sys.exit(1)

    driver = get_driver()
    init_schema(driver)

    for taxon_id in DEMO_SPECIES:
        ingest_species(taxon_id, driver)

    close_driver()
    logger.info("")
    logger.info("Demo seed complete!")
    logger.info("Start the backend: uvicorn app.main:app --reload --port 8000")
    logger.info("Start the frontend: cd frontend && npm run dev")


if __name__ == "__main__":
    main()
