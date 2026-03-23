"""
Ingestion Patcher for Gene-Intel.

Reads the JSON report from check_ingestion.py (or re-runs checks live),
then re-runs only the failed steps for each species.

What it can patch:
  - Missing/empty GTF or BioMart files → prints download instructions (cannot auto-download)
  - Missing Neo4j schema → calls init_schema()
  - Missing Species node / zero genes/transcripts/features → re-runs GTF step
  - Zero or low domain coverage → re-runs domain ingestion step
  - Missing CO_LOCATED_WITH edges → re-runs GTF step (edges are built during GTF ingest)

Usage:
    cd backend/

    # Run checks fresh and patch whatever fails:
    python scripts/patch_ingest.py

    # Feed a previously saved JSON report:
    python scripts/patch_ingest.py --report check_report.json

    # Dry-run: print what would be re-run without doing it:
    python scripts/patch_ingest.py --dry-run

    # Patch a single species only:
    python scripts/patch_ingest.py --species 9606

    # Patch schema only (no data re-ingestion):
    python scripts/patch_ingest.py --schema-only
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.ingestion.run_ingest import SPECIES_REGISTRY, _WELL_ANNOTATED, _auto_select_domain_route

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_report(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def _run_checks() -> dict:
    """Re-run checks live (imports check_ingestion inline to avoid circular import)."""
    check_script = Path(__file__).parent / "check_ingestion.py"
    spec_dir = str(check_script.parent.parent)
    sys.path.insert(0, spec_dir)

    from scripts.check_ingestion import check_files, check_schema, check_neo4j_data
    from app.db.neo4j_client import get_driver, close_driver

    driver = get_driver()
    report = {
        "files": check_files(),
        "schema": check_schema(driver),
        "data": check_neo4j_data(driver),
    }
    close_driver()   # resets the _driver global so get_driver() creates a fresh connection below
    return report


def _gtf_file_exists(taxon: str) -> bool:
    meta = SPECIES_REGISTRY[taxon]
    p = Path(settings.gtf_data_dir) / meta["gtf_filename"]
    return p.exists() and p.stat().st_size > 0


def _print_download_hint(taxon: str) -> None:
    meta = SPECIES_REGISTRY[taxon]
    gtf_dir = os.path.abspath(settings.gtf_data_dir)
    bm_dir  = os.path.abspath(settings.biomart_data_dir)

    print(f"\n  [MANUAL ACTION REQUIRED] Missing files for {meta['common_name']} (taxon {taxon}):")
    gtf_p = Path(settings.gtf_data_dir) / meta["gtf_filename"]
    if not (gtf_p.exists() and gtf_p.stat().st_size > 0):
        print(f"    GTF  → place '{meta['gtf_filename']}' in {gtf_dir}/")
        if meta["gtf_source"] == "ensembl":
            print(f"    Download from: https://ftp.ensembl.org/pub/current_gtf/")
        else:
            print(f"    Download from: https://ftp.ncbi.nlm.nih.gov/genomes/")

    if meta["biomart_filename"]:
        bm_p = Path(settings.biomart_data_dir) / meta["biomart_filename"]
        if not (bm_p.exists() and bm_p.stat().st_size > 0):
            print(f"    BioMart → place '{meta['biomart_filename']}' in {bm_dir}/")
            print(f"    Export from: https://www.ensembl.org/biomart/martview")


# ── Patch actions ──────────────────────────────────────────────────────────────

def patch_schema(driver, dry_run: bool = False) -> None:
    from app.db.schema import init_schema
    if dry_run:
        print("  [DRY-RUN] Would run: init_schema()")
        return
    logger.info("Applying missing schema (constraints + indexes)…")
    init_schema(driver)
    logger.info("Schema applied.")


def patch_gtf(taxon: str, driver, dry_run: bool = False) -> None:
    from app.ingestion.run_ingest import ingest_species
    if dry_run:
        print(f"  [DRY-RUN] Would run: ingest_species('{taxon}', driver)  [GTF + edges + BioMart domains]")
        return
    logger.info("Re-running GTF ingestion for taxon %s…", taxon)
    ingest_species(taxon, driver)


def patch_domains(taxon: str, driver, dry_run: bool = False) -> None:
    from app.ingestion.run_ingest import run_domain_ingest
    source = _auto_select_domain_route(int(taxon))
    if dry_run:
        print(f"  [DRY-RUN] Would run: run_domain_ingest('{taxon}', driver, domain_source='{source}')")
        return
    logger.info("Re-running domain ingestion for taxon %s (source=%s)…", taxon, source)
    run_domain_ingest(taxon, driver, domain_source=source)


# ── Decision logic ─────────────────────────────────────────────────────────────

def decide_patches(report: dict, only_taxon: str | None = None) -> list[dict]:
    """
    Return an ordered list of patch actions derived from the report.

    Each action is a dict:
        {"action": "schema" | "gtf" | "domains" | "manual_file",
         "taxon": str | None,
         "reason": str}
    """
    actions = []

    # Schema
    schema = report.get("schema", {})
    if schema and not schema.get("ok"):
        actions.append({
            "action": "schema",
            "taxon": None,
            "reason": (
                f"missing constraints={schema.get('missing_constraints', [])} "
                f"indexes={schema.get('missing_indexes', [])}"
            ),
        })

    # Per-species
    file_results = report.get("files", {})
    data_results = report.get("data", {})

    taxons = [only_taxon] if only_taxon else sorted(SPECIES_REGISTRY.keys())

    for taxon in taxons:
        if taxon not in SPECIES_REGISTRY:
            logger.warning("Unknown taxon %s — skipping", taxon)
            continue

        file_r = file_results.get(taxon, {})
        data_r = data_results.get(taxon, {})

        # ── File issues → manual download required ──────────────────────────
        gtf_ok  = file_r.get("gtf", {}).get("ok", True)
        bm_info = file_r.get("biomart")
        bm_ok   = bm_info.get("ok", True) if bm_info is not None else True

        if not gtf_ok or not bm_ok:
            actions.append({
                "action": "manual_file",
                "taxon": taxon,
                "reason": "GTF or BioMart file missing/empty",
            })
            # Cannot proceed with GTF/domain patch without the file
            continue

        # ── Data issues ─────────────────────────────────────────────────────
        if not data_r:
            continue

        issues = data_r.get("issues", [])
        needs_gtf = (
            "species node missing from Neo4j" in issues
            or data_r.get("genes", 0) == 0
            or data_r.get("transcripts", 0) == 0
            or data_r.get("features", 0) == 0
            or any("no CO_LOCATED_WITH" in i for i in issues)
            or any("genes" in i and "< threshold" in i for i in issues)
        )
        needs_domains = any(
            "domain coverage" in i or "no domains" in i for i in issues
        )

        if needs_gtf:
            actions.append({
                "action": "gtf",
                "taxon": taxon,
                "reason": "; ".join(i for i in issues if "domain" not in i),
            })
            # GTF step also re-writes BioMart domains so domain step may be redundant,
            # but queue domain patch too for low-coverage species
            if int(taxon) not in _WELL_ANNOTATED:
                actions.append({
                    "action": "domains",
                    "taxon": taxon,
                    "reason": "Low-coverage species — re-running domain enrichment after GTF fix",
                })
        elif needs_domains:
            actions.append({
                "action": "domains",
                "taxon": taxon,
                "reason": "; ".join(i for i in issues if "domain" in i),
            })

    return actions


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Gene-Intel ingestion patcher")
    parser.add_argument("--report", metavar="FILE", help="Path to JSON report from check_ingestion.py")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done without doing it")
    parser.add_argument("--species", metavar="TAXON_ID", help="Patch a single species only")
    parser.add_argument("--schema-only", action="store_true", help="Only fix schema, skip data re-ingestion")
    args = parser.parse_args()

    # ── Load or generate report ────────────────────────────────────────────────
    if args.report:
        logger.info("Loading report from %s", args.report)
        report = _load_report(args.report)
    else:
        logger.info("Running live checks…")
        try:
            report = _run_checks()
        except Exception as exc:
            logger.error("Failed to connect to Neo4j: %s", exc)
            logger.info("Tip: run file-only checks with: python scripts/check_ingestion.py --no-neo4j")
            sys.exit(1)

    if report.get("overall_ok"):
        print("All checks passed — nothing to patch.")
        sys.exit(0)

    # ── Decide what to patch ───────────────────────────────────────────────────
    actions = decide_patches(report, only_taxon=args.species)

    if args.schema_only:
        actions = [a for a in actions if a["action"] == "schema"]

    if not actions:
        print("No patchable issues found (there may be manual actions required — see above).")
        sys.exit(0)

    # ── Print plan ─────────────────────────────────────────────────────────────
    print(f"\n{'DRY-RUN: ' if args.dry_run else ''}Patch plan ({len(actions)} actions):")
    for i, a in enumerate(actions, 1):
        taxon_label = f" [{SPECIES_REGISTRY[a['taxon']]['common_name']}]" if a["taxon"] else ""
        print(f"  {i}. {a['action'].upper()}{taxon_label}  — {a['reason']}")

    # ── Print manual-file hints before proceeding ──────────────────────────────
    manual_taxons = [a["taxon"] for a in actions if a["action"] == "manual_file"]
    for taxon in manual_taxons:
        _print_download_hint(taxon)

    if args.dry_run:
        print("\nDry-run complete. Re-run without --dry-run to apply patches.")
        sys.exit(0)

    # ── Execute patches ────────────────────────────────────────────────────────
    try:
        from app.db.neo4j_client import get_driver
        driver = get_driver()
    except Exception as exc:
        logger.error("Cannot connect to Neo4j: %s", exc)
        sys.exit(1)

    errors = []
    for a in actions:
        if a["action"] == "manual_file":
            continue  # already printed hints above
        try:
            if a["action"] == "schema":
                patch_schema(driver, dry_run=False)
            elif a["action"] == "gtf":
                patch_gtf(a["taxon"], driver, dry_run=False)
            elif a["action"] == "domains":
                patch_domains(a["taxon"], driver, dry_run=False)
        except Exception as exc:
            logger.error("Action %s taxon=%s failed: %s", a["action"], a["taxon"], exc)
            errors.append((a, str(exc)))

    driver.close()

    print()
    if errors:
        print(f"Patch completed with {len(errors)} error(s):")
        for a, msg in errors:
            print(f"  ✗ {a['action']} taxon={a['taxon']}: {msg}")
        print("\nRe-run check_ingestion.py to see remaining issues.")
        sys.exit(1)
    else:
        print("All patches applied successfully.")
        print("Run check_ingestion.py to verify.")
        sys.exit(0)


if __name__ == "__main__":
    main()
