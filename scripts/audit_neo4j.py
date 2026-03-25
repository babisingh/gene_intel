#!/usr/bin/env python3
"""
Neo4j ingestion audit for Gene-Intel.

Connects to Neo4j (reads credentials from .env or .env_local) and reports:
  - Which species nodes exist
  - Gene / transcript / feature / domain counts per species
  - What's missing vs the expected 17-species registry
  - Schema health (constraints + indexes)

Usage (run from repo root):
    python scripts/audit_neo4j.py
    python scripts/audit_neo4j.py --env backend/.env_local
    python scripts/audit_neo4j.py --uri "neo4j+s://xxx.databases.neo4j.io" \
                                   --user neo4j --password secret
"""

from __future__ import annotations

import argparse
import os
import sys

# ── allow running from repo root without installing the package ───────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))


# ── expected species registry (mirrors run_ingest.py) ────────────────────────
EXPECTED_SPECIES = {
    "9606":   ("Homo sapiens",               "Human"),
    "10090":  ("Mus musculus",               "Mouse"),
    "7955":   ("Danio rerio",                "Zebrafish"),
    "9031":   ("Gallus gallus",              "Chicken"),
    "8364":   ("Xenopus tropicalis",         "Western clawed frog"),
    "9598":   ("Pan troglodytes",            "Chimpanzee"),
    "7227":   ("Drosophila melanogaster",    "Fruit fly"),
    "6239":   ("Caenorhabditis elegans",     "Roundworm"),
    "3702":   ("Arabidopsis thaliana",       "Thale cress"),
    "4530":   ("Oryza sativa",               "Rice"),
    "3218":   ("Physcomitrium patens",       "Moss"),
    "3055":   ("Chlamydomonas reinhardtii",  "Green alga"),
    "162425": ("Aspergillus niger",          "Black mould"),
    "4932":   ("Saccharomyces cerevisiae",   "Yeast"),
    "511145": ("Escherichia coli K-12",      "E. coli K-12"),
    "9913":   ("Bos taurus",                 "Cow"),
    "8665":   ("Ophiophagus hannah",         "King cobra"),
}

# Minimum acceptable domain coverage % before we flag a species
DOMAIN_COVERAGE_WARN  = 30.0
DOMAIN_COVERAGE_ALERT = 10.0


# ─────────────────────────────────────────────────────────────────────────────

def connect(uri: str, user: str, password: str):
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    return driver


def q(session, cypher: str, **params):
    return list(session.run(cypher, **params))


def run_audit(driver) -> None:
    with driver.session() as s:

        # ── 1. Schema health ──────────────────────────────────────────────────
        constraints = q(s, "SHOW CONSTRAINTS")
        indexes     = q(s, "SHOW INDEXES")
        print("\n── Schema ───────────────────────────────────────────────────")
        print(f"  Constraints : {len(constraints)}")
        print(f"  Indexes     : {len(indexes)}")
        if len(constraints) < 5 or len(indexes) < 9:
            print("  ⚠  Schema looks incomplete — run: python scripts/init_schema.py")

        # ── 2. Top-level node counts ──────────────────────────────────────────
        totals = q(s, """
            MATCH (n)
            RETURN labels(n)[0] AS label, count(n) AS cnt
            ORDER BY cnt DESC
        """)
        print("\n── Total node counts ────────────────────────────────────────")
        for row in totals:
            print(f"  {row['label']:<14} {row['cnt']:>10,}")

        rel_totals = q(s, """
            MATCH ()-[r]->()
            RETURN type(r) AS rel, count(r) AS cnt
            ORDER BY cnt DESC
        """)
        print("\n── Relationship counts ──────────────────────────────────────")
        for row in rel_totals:
            print(f"  {row['rel']:<22} {row['cnt']:>10,}")

        # ── 3. Per-species breakdown ──────────────────────────────────────────
        species_rows = q(s, """
            MATCH (sp:Species)
            OPTIONAL MATCH (sp)-[:HAS_GENE]->(g:Gene)
            OPTIONAL MATCH (g)-[:HAS_TRANSCRIPT]->(t:Transcript)
            OPTIONAL MATCH (g)-[:HAS_FEATURE]->(f:Feature)
            OPTIONAL MATCH (g)-[:HAS_DOMAIN]->(d:Domain)
            RETURN
                sp.taxon_id     AS taxon,
                sp.common_name  AS name,
                sp.assembly     AS assembly,
                count(DISTINCT g) AS genes,
                count(DISTINCT t) AS transcripts,
                count(DISTINCT f) AS features,
                count(DISTINCT d) AS domains
            ORDER BY genes DESC
        """)

        print("\n── Per-species breakdown ────────────────────────────────────────────────────────────")
        header = f"  {'Taxon':<8} {'Name':<22} {'Genes':>7} {'Tx':>7} {'Feat':>7} {'Domains':>8} {'Dom%':>6}  Assembly"
        print(header)
        print("  " + "─" * (len(header) - 2))

        ingested_taxons: set[str] = set()
        flagged: list[str] = []

        for row in species_rows:
            taxon      = str(row["taxon"])
            name       = row["name"] or "?"
            genes      = row["genes"] or 0
            txs        = row["transcripts"] or 0
            feats      = row["features"] or 0
            domains    = row["domains"] or 0
            assembly   = row["assembly"] or "?"
            coverage   = (domains / genes * 100) if genes > 0 else 0.0

            ingested_taxons.add(taxon)

            flag = "  "
            if genes == 0:
                flag = "✗ "
                flagged.append(f"taxon {taxon} ({name}): 0 genes — ingest may have failed")
            elif coverage < DOMAIN_COVERAGE_ALERT:
                flag = "⚠ "
                flagged.append(f"taxon {taxon} ({name}): domain coverage {coverage:.1f}% [ALERT < {DOMAIN_COVERAGE_ALERT}%]")
            elif coverage < DOMAIN_COVERAGE_WARN:
                flag = "! "
                flagged.append(f"taxon {taxon} ({name}): domain coverage {coverage:.1f}% [WARN < {DOMAIN_COVERAGE_WARN}%]")

            print(
                f"{flag}{'%-8s' % taxon} {'%-22s' % name} "
                f"{genes:>7,} {txs:>7,} {feats:>7,} {domains:>8,} {coverage:>5.1f}%  {assembly}"
            )

        # ── 4. Missing species ────────────────────────────────────────────────
        missing = {k: v for k, v in EXPECTED_SPECIES.items() if k not in ingested_taxons}

        print("\n── Missing species (not yet ingested) ───────────────────────")
        if missing:
            for taxon, (sci, common) in missing.items():
                print(f"  ✗  taxon {taxon:<8} {common} ({sci})")
        else:
            print("  ✓  All 17 species present")

        # ── 5. Flags summary ──────────────────────────────────────────────────
        if flagged:
            print("\n── Issues to fix ────────────────────────────────────────────")
            for msg in flagged:
                print(f"  • {msg}")
        else:
            print("\n  ✓  No issues found")

        print()


# ─────────────────────────────────────────────────────────────────────────────

def load_dotenv(path: str) -> dict[str, str]:
    """Minimal dotenv loader — no dependency on python-dotenv."""
    env: dict[str, str] = {}
    if not os.path.exists(path):
        return env
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Gene-Intel Neo4j ingestion state")
    parser.add_argument("--env",      default=None,    help="Path to .env file (default: auto-detect)")
    parser.add_argument("--uri",      default=None,    help="Neo4j URI (overrides .env)")
    parser.add_argument("--user",     default=None,    help="Neo4j user (overrides .env)")
    parser.add_argument("--password", default=None,    help="Neo4j password (overrides .env)")
    args = parser.parse_args()

    # Credential resolution order: CLI args > .env file > environment vars > defaults
    env: dict[str, str] = {}

    if args.env:
        env = load_dotenv(args.env)
    else:
        # Auto-detect: try several common locations
        for candidate in [
            "backend/.env_local", ".env_local",
            "backend/.env", ".env",
        ]:
            if os.path.exists(candidate):
                env = load_dotenv(candidate)
                print(f"  (loaded credentials from {candidate})")
                break

    uri      = args.uri      or env.get("NEO4J_URI")      or os.getenv("NEO4J_URI")      or "bolt://localhost:7687"
    user     = args.user     or env.get("NEO4J_USER")     or os.getenv("NEO4J_USER")     or "neo4j"
    password = args.password or env.get("NEO4J_PASSWORD") or os.getenv("NEO4J_PASSWORD") or "password"

    print(f"\nGene-Intel Neo4j Audit")
    print(f"  URI  : {uri}")
    print(f"  User : {user}")

    try:
        driver = connect(uri, user, password)
    except Exception as exc:
        print(f"\n✗  Cannot connect to Neo4j: {exc}")
        print("   Check credentials or use --uri / --password flags.")
        sys.exit(1)

    try:
        run_audit(driver)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
