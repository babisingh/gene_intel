#!/usr/bin/env python3
"""
One-time Neo4j schema initialisation.

Run this once before the first ingestion:
    python scripts/init_schema.py

Safe to re-run — uses IF NOT EXISTS guards.
"""

import sys
import os

# Add backend/ to PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.db.neo4j_client import get_driver, verify_connectivity, close_driver
from app.db.schema import init_schema, CONSTRAINTS, INDEXES
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
logger = logging.getLogger(__name__)


def main():
    logger.info("Connecting to Neo4j…")
    if not verify_connectivity():
        logger.error("Cannot connect to Neo4j. Check NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD in .env")
        sys.exit(1)

    driver = get_driver()
    logger.info("Applying %d constraints and %d indexes…", len(CONSTRAINTS), len(INDEXES))
    init_schema(driver)
    logger.info("Schema initialisation complete.")
    close_driver()


if __name__ == "__main__":
    main()
