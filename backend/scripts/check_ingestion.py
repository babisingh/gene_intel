"""
Ingestion Validator for Gene-Intel.

Checks:
  1. Required data files (GTF, BioMart TSV) — exist and non-empty
  2. Neo4j schema — all constraints and indexes present
  3. Neo4j data — Species nodes, Gene/Transcript/Feature/Domain counts,
     CO_LOCATED_WITH edges — for all 17 species

Exits with code 0 if everything looks OK, 1 if any issues found.

Usage:
    cd backend/
    python scripts/check_ingestion.py
    python scripts/check_ingestion.py --json   # machine-readable report
    python scripts/check_ingestion.py --no-neo4j  # file checks only
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Allow running from backend/ as well as project root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.ingestion.run_ingest import SPECIES_REGISTRY, _WELL_ANNOTATED

# ── Thresholds ─────────────────────────────────────────────────────────────────
# A species with fewer genes than this is almost certainly incomplete.
MIN_GENES: dict[str, int] = {
    "9606":   19_000,   # Human
    "10090":  20_000,   # Mouse
    "7955":   22_000,   # Zebrafish
    "9031":   14_000,   # Chicken
    "8364":   19_000,   # Xenopus
    "9598":   19_000,   # Chimpanzee
    "9913":   19_000,   # Cow
    "7227":   13_000,   # Drosophila
    "6239":   17_000,   # C. elegans
    "3702":   25_000,   # Arabidopsis
    "4530":   37_000,   # Rice
    "3218":   27_000,   # Moss
    "3055":   14_000,   # Green alga
    "162425":  9_000,   # Aspergillus niger
    "4932":    5_000,   # Yeast
    "511145":  4_000,   # E. coli K-12
    "8665":   18_000,   # King cobra
}

# Minimum domain coverage % expected per species
MIN_DOMAIN_COVERAGE_PCT: dict[str, float] = {
    taxon: (15.0 if taxon not in [str(t) for t in _WELL_ANNOTATED] else 25.0)
    for taxon in SPECIES_REGISTRY
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def _check_file(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {"ok": False, "reason": "missing"}
    size = p.stat().st_size
    if size == 0:
        return {"ok": False, "reason": "empty"}
    return {"ok": True, "size_bytes": size}


def check_files() -> dict:
    """Check that all expected input data files are present and non-empty."""
    results = {}
    for taxon, meta in SPECIES_REGISTRY.items():
        gtf_path = os.path.join(settings.gtf_data_dir, meta["gtf_filename"])
        gtf_check = _check_file(gtf_path)

        bm_check = None
        if meta["biomart_filename"]:
            bm_path = os.path.join(settings.biomart_data_dir, meta["biomart_filename"])
            bm_check = _check_file(bm_path)

        ok = gtf_check["ok"] and (bm_check is None or bm_check["ok"])
        results[taxon] = {
            "common_name": meta["common_name"],
            "ok": ok,
            "gtf": gtf_check,
            "biomart": bm_check,
        }
    return results


# ── Neo4j checks ───────────────────────────────────────────────────────────────

def check_schema(driver) -> dict:
    """Verify all expected constraints and indexes exist in Neo4j."""
    from app.db.schema import CONSTRAINTS, INDEXES

    def _names(ddl_list):
        """Extract the constraint/index name from each CREATE … statement."""
        names = []
        for stmt in ddl_list:
            # e.g. "CREATE CONSTRAINT species_taxon IF NOT EXISTS …"
            parts = stmt.split()
            names.append(parts[2])   # index 2 is the name
        return names

    expected_constraints = set(_names(CONSTRAINTS))
    expected_indexes = set(_names(INDEXES))

    with driver.session() as s:
        existing_constraints = {
            r["name"] for r in s.run("SHOW CONSTRAINTS YIELD name")
        }
        existing_indexes = {
            r["name"] for r in s.run("SHOW INDEXES YIELD name")
        }

    missing_constraints = expected_constraints - existing_constraints
    missing_indexes = expected_indexes - existing_indexes

    return {
        "ok": not missing_constraints and not missing_indexes,
        "missing_constraints": sorted(missing_constraints),
        "missing_indexes": sorted(missing_indexes),
    }


def check_neo4j_data(driver) -> dict:
    """Check node/relationship counts per species."""
    query = """
    MATCH (s:Species)
    OPTIONAL MATCH (s)-[:HAS_GENE]->(g:Gene)
    OPTIONAL MATCH (g)-[:HAS_TRANSCRIPT]->(t:Transcript)
    OPTIONAL MATCH (t)-[:HAS_FEATURE]->(f:Feature)
    OPTIONAL MATCH (g)-[:HAS_DOMAIN]->(d:Domain)
    WITH s.taxon_id AS taxon,
         s.common_name AS common_name,
         count(DISTINCT g) AS genes,
         count(DISTINCT t) AS transcripts,
         count(DISTINCT f) AS features,
         count(DISTINCT d) AS domains
    RETURN taxon, common_name, genes, transcripts, features, domains
    ORDER BY taxon
    """

    coloc_query = """
    MATCH (s:Species)-[:HAS_GENE]->(g:Gene)-[r:CO_LOCATED_WITH]->()
    RETURN s.taxon_id AS taxon, count(r) AS edges
    """

    with driver.session() as s:
        rows = list(s.run(query))
        coloc_rows = list(s.run(coloc_query))

    coloc_by_taxon = {r["taxon"]: r["edges"] for r in coloc_rows}

    ingested_taxons = {r["taxon"] for r in rows}
    missing_species = set(SPECIES_REGISTRY.keys()) - ingested_taxons

    results = {}
    for row in rows:
        taxon = row["taxon"]
        genes = row["genes"]
        transcripts = row["transcripts"]
        features = row["features"]
        domains = row["domains"]
        coloc = coloc_by_taxon.get(taxon, 0)
        min_genes = MIN_GENES.get(taxon, 1)
        min_cov = MIN_DOMAIN_COVERAGE_PCT.get(taxon, 10.0)
        domain_pct = (domains / genes * 100) if genes > 0 else 0.0

        issues = []
        if genes < min_genes:
            issues.append(f"genes {genes} < threshold {min_genes}")
        if transcripts == 0:
            issues.append("no transcripts")
        if features == 0:
            issues.append("no features")
        if coloc == 0:
            issues.append("no CO_LOCATED_WITH edges")
        if domain_pct < min_cov:
            issues.append(f"domain coverage {domain_pct:.1f}% < threshold {min_cov:.1f}%")

        results[taxon] = {
            "common_name": row["common_name"],
            "ok": len(issues) == 0,
            "issues": issues,
            "genes": genes,
            "transcripts": transcripts,
            "features": features,
            "domains": domains,
            "coloc_edges": coloc,
            "domain_coverage_pct": round(domain_pct, 1),
        }

    for taxon in missing_species:
        results[taxon] = {
            "common_name": SPECIES_REGISTRY[taxon]["common_name"],
            "ok": False,
            "issues": ["species node missing from Neo4j"],
            "genes": 0,
            "transcripts": 0,
            "features": 0,
            "domains": 0,
            "coloc_edges": 0,
            "domain_coverage_pct": 0.0,
        }

    return results


# ── Reporting ──────────────────────────────────────────────────────────────────

def _print_file_report(file_results: dict) -> bool:
    ok_all = True
    print("\n── Data Files ─────────────────────────────────────────────────────")
    print(f"  {'Taxon':<8} {'Species':<22} {'GTF':<12} {'BioMart':<12} Status")
    print("  " + "-" * 72)
    for taxon, r in sorted(file_results.items()):
        gtf = "OK" if r["gtf"]["ok"] else r["gtf"]["reason"].upper()
        bm  = "OK" if r["biomart"] is None else ("OK" if r["biomart"]["ok"] else r["biomart"]["reason"].upper())
        bm  = "N/A" if r["biomart"] is None else bm
        status = "✓" if r["ok"] else "✗ FAIL"
        print(f"  {taxon:<8} {r['common_name']:<22} {gtf:<12} {bm:<12} {status}")
        if not r["ok"]:
            ok_all = False
    return ok_all


def _print_schema_report(schema: dict) -> bool:
    print("\n── Neo4j Schema ───────────────────────────────────────────────────")
    if schema["ok"]:
        print("  All constraints and indexes present. ✓")
    else:
        if schema["missing_constraints"]:
            print(f"  Missing constraints: {schema['missing_constraints']}")
        if schema["missing_indexes"]:
            print(f"  Missing indexes: {schema['missing_indexes']}")
        print("  ✗ FAIL")
    return schema["ok"]


def _print_data_report(data_results: dict) -> bool:
    ok_all = True
    print("\n── Neo4j Data ─────────────────────────────────────────────────────")
    print(f"  {'Taxon':<8} {'Species':<22} {'Genes':>7} {'Tx':>7} {'Feat':>7} {'Domains':>8} {'Cov%':>6}  Issues")
    print("  " + "-" * 90)
    for taxon, r in sorted(data_results.items()):
        status = "✓" if r["ok"] else "✗"
        issues_str = "; ".join(r["issues"]) if r["issues"] else ""
        print(
            f"  {taxon:<8} {r['common_name']:<22} {r['genes']:>7} {r['transcripts']:>7} "
            f"{r['features']:>7} {r['domains']:>8} {r['domain_coverage_pct']:>5.1f}%  "
            f"{status} {issues_str}"
        )
        if not r["ok"]:
            ok_all = False
    return ok_all


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Gene-Intel ingestion validator")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument("--no-neo4j", action="store_true", help="Skip Neo4j checks (file checks only)")
    args = parser.parse_args()

    report = {}
    overall_ok = True

    # ── File checks ────────────────────────────────────────────────────────────
    print("Checking data files…")
    file_results = check_files()
    report["files"] = file_results
    files_ok = all(r["ok"] for r in file_results.values())
    if not files_ok:
        overall_ok = False

    # ── Neo4j checks ───────────────────────────────────────────────────────────
    schema_results = None
    data_results = None

    if not args.no_neo4j:
        try:
            from app.db.neo4j_client import get_driver
            driver = get_driver()

            print("Checking Neo4j schema…")
            schema_results = check_schema(driver)
            report["schema"] = schema_results
            if not schema_results["ok"]:
                overall_ok = False

            print("Checking Neo4j data…")
            data_results = check_neo4j_data(driver)
            report["data"] = data_results
            if not all(r["ok"] for r in data_results.values()):
                overall_ok = False

            driver.close()
        except Exception as exc:
            print(f"ERROR connecting to Neo4j: {exc}", file=sys.stderr)
            report["neo4j_error"] = str(exc)
            overall_ok = False

    report["overall_ok"] = overall_ok

    # ── Output ─────────────────────────────────────────────────────────────────
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_file_report(file_results)
        if schema_results is not None:
            _print_schema_report(schema_results)
        if data_results is not None:
            _print_data_report(data_results)
        print()
        if overall_ok:
            print("Overall: ALL CHECKS PASSED ✓")
        else:
            print("Overall: ISSUES FOUND ✗  (run patch_ingest.py to fix)")

    sys.exit(0 if overall_ok else 1)


if __name__ == "__main__":
    main()
