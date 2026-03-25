"""
CLI entrypoint for the Gene-Intel ingestion pipeline.

Usage:
    python -m app.ingestion.run_ingest --species 9606
    python -m app.ingestion.run_ingest --species 511145   # E. coli (GFF3 auto-detected)
    python -m app.ingestion.run_ingest --all              # All 17 species

    # Domain ingestion
    python -m app.ingestion.run_ingest --species 9606 --step domains
    python -m app.ingestion.run_ingest --species 9606 --domain-source uniprot
    python -m app.ingestion.run_ingest --species 175781 --domain-source interproscan

    # Coverage report
    python -m app.ingestion.run_ingest domains --report

Species metadata is defined in SPECIES_REGISTRY below.
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone

# Ensure backend/ is on PYTHONPATH when run as module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from app.config import settings
from app.db.neo4j_client import get_driver
from app.db.schema import init_schema
from app.ingestion.dialect_detector import detect_dialect
from app.ingestion.gtf_parser import parse_gtf_streaming
from app.ingestion.feature_extractor import extract_features
from app.ingestion.biomart_parser import parse_biomart_tsv, extract_domains_from_gff3_attrs
from app.ingestion.neighborhood_builder import build_neighborhood_edges
from app.ingestion.batch_writer import (
    write_species_node,
    write_genes_batch,
    write_transcripts_batch,
    write_features_batch,
    write_domains_batch,
    write_edges_batch,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ── Species Registry ──────────────────────────────────────────────────────────
SPECIES_REGISTRY = {
    "9606": {
        "name": "Homo sapiens", "common_name": "Human", "kingdom": "Animalia",
        "assembly": "GRCh38.p14", "gtf_source": "ensembl",
        "gtf_filename": "homo_sapiens.gtf.gz",
        "biomart_filename": "biomart_9606.tsv",
    },
    "10090": {
        "name": "Mus musculus", "common_name": "Mouse", "kingdom": "Animalia",
        "assembly": "GRCm39", "gtf_source": "ensembl",
        "gtf_filename": "mus_musculus.gtf.gz",
        "biomart_filename": "biomart_10090.tsv",
    },
    "7955": {
        "name": "Danio rerio", "common_name": "Zebrafish", "kingdom": "Animalia",
        "assembly": "GRCz11", "gtf_source": "ensembl",
        "gtf_filename": "danio_rerio.gtf.gz",
        "biomart_filename": "biomart_7955.tsv",
    },
    "9031": {
        "name": "Gallus gallus", "common_name": "Chicken", "kingdom": "Animalia",
        "assembly": "bGalGal1.mat.broiler.GRCg7b", "gtf_source": "ensembl",
        "gtf_filename": "gallus_gallus.gtf.gz",
        "biomart_filename": "biomart_9031.tsv",
    },
    "8364": {
        "name": "Xenopus tropicalis", "common_name": "Western clawed frog", "kingdom": "Animalia",
        "assembly": "UCB_Xtro_10.0", "gtf_source": "ensembl",
        "gtf_filename": "xenopus_tropicalis.gtf.gz",
        "biomart_filename": "biomart_8364.tsv",
    },
    "9598": {
        "name": "Pan troglodytes", "common_name": "Chimpanzee", "kingdom": "Animalia",
        "assembly": "Pan_tro_3.0", "gtf_source": "ensembl",
        "gtf_filename": "pan_troglodytes.gtf.gz",
        "biomart_filename": "biomart_9598.tsv",
    },
    "7227": {
        "name": "Drosophila melanogaster", "common_name": "Fruit fly", "kingdom": "Invertebrata",
        "assembly": "BDGP6.46", "gtf_source": "ensembl",
        "gtf_filename": "drosophila_melanogaster.gtf.gz",
        "biomart_filename": "biomart_7227.tsv",
    },
    "6239": {
        "name": "Caenorhabditis elegans", "common_name": "Roundworm", "kingdom": "Invertebrata",
        "assembly": "WBcel235", "gtf_source": "ensembl",
        "gtf_filename": "caenorhabditis_elegans.gtf.gz",
        "biomart_filename": "biomart_6239.tsv",
    },
    "3702": {
        "name": "Arabidopsis thaliana", "common_name": "Thale cress", "kingdom": "Plantae",
        "assembly": "TAIR10", "gtf_source": "ensembl",
        "gtf_filename": "arabidopsis_thaliana.gtf.gz",
        "biomart_filename": "biomart_3702.tsv",
    },
    "4530": {
        "name": "Oryza sativa", "common_name": "Rice", "kingdom": "Plantae",
        "assembly": "IRGSP-1.0", "gtf_source": "ensembl",
        "gtf_filename": "oryza_sativa.gtf.gz",
        "biomart_filename": "biomart_4530.tsv",
    },
    "3218": {
        "name": "Physcomitrium patens", "common_name": "Moss", "kingdom": "Bryophyta",
        "assembly": "Phypa_V3", "gtf_source": "ensembl",
        "gtf_filename": "physcomitrium_patens.gtf.gz",
        "biomart_filename": "biomart_3218.tsv",
    },
    "3055": {
        "name": "Chlamydomonas reinhardtii", "common_name": "Green alga", "kingdom": "Algae",
        "assembly": "Chlamydomonas_reinhardtii_v5.5", "gtf_source": "ensembl",
        "gtf_filename": "chlamydomonas_reinhardtii.gtf.gz",
        "biomart_filename": "biomart_3055.tsv",
    },
    "162425": {
        "name": "Aspergillus niger", "common_name": "Black mould", "kingdom": "Fungi",
        "assembly": "ASM285v2", "gtf_source": "ensembl",
        "gtf_filename": "aspergillus_niger.gtf.gz",
        "biomart_filename": "biomart_162425.tsv",
    },
    "4932": {
        "name": "Saccharomyces cerevisiae", "common_name": "Yeast", "kingdom": "Fungi",
        "assembly": "R64-1-1", "gtf_source": "ensembl",
        "gtf_filename": "saccharomyces_cerevisiae.gtf.gz",
        "biomart_filename": "biomart_4932.tsv",
    },
    "511145": {
        "name": "Escherichia coli K-12", "common_name": "E. coli K-12", "kingdom": "Bacteria",
        "assembly": "ASM584v2", "gtf_source": "ncbi_gff3",
        "gtf_filename": "ecoli_k12.gff3.gz",
        "biomart_filename": None,  # E. coli uses GFF3 Dbxref
    },
    # ── Species 16-17 (added 2025) ────────────────────────────────────────────
    "9913": {
        "name": "Bos taurus", "common_name": "Cow", "kingdom": "Animalia",
        "assembly": "ARS-UCD1.3", "gtf_source": "ensembl",
        "ensembl_name": "bos_taurus",
        "gtf_filename": "bos_taurus.gtf.gz",
        "biomart_filename": "biomart_9913.tsv",
        "uniprot_proteome": "UP000009136",
        "annotation_note": "Well-annotated agricultural genome, ~22,000 protein-coding genes",
    },
    "8665": {
        "name": "Ophiophagus hannah", "common_name": "King cobra", "kingdom": "Reptilia",
        "assembly": "OphHan1.0", "gtf_source": "ensembl",
        "ensembl_name": "ophiophagus_hannah",
        "gtf_filename": "ophiophagus_hannah.gtf.gz",
        "biomart_filename": "biomart_8665.tsv",
        "uniprot_proteome": "UP000308820",
        "annotation_note": "Venom-related gene clusters, complex alternative splicing patterns",
    },
}


# Species with good Swiss-Prot (reviewed) coverage — use reviewed_only=True
_WELL_ANNOTATED = {9606, 10090, 7955, 9031, 9598, 7227, 6239, 3702, 4530, 4932, 9913}
# Species needing TrEMBL fallback or InterProScan
_LOW_COVERAGE = {175781, 3218, 3055, 162425, 511145, 8665}


def _auto_select_domain_route(taxon_id: int) -> str:
    """Return the recommended domain source for a given taxon."""
    if taxon_id in _WELL_ANNOTATED:
        return "both"          # UniProt reviewed + InterPro enrichment
    return "both_unreviewed"   # UniProt unreviewed + InterPro + possibly InterProScan


def run_domain_ingest(
    taxon_id_str: str,
    driver,
    domain_source: str = "both",
    skip_enrichment: bool = False,
    ftp_file: str | None = None,
) -> None:
    """Run domain ingestion for one species using the requested route(s)."""
    from app.ingestion.domain_ingest_uniprot import run_uniprot_domain_ingest
    from app.ingestion.domain_ingest_interpro import enrich_existing_domains
    from app.ingestion.domain_ingest_ftp import run_ftp_domain_ingest
    from app.ingestion.domain_ingest_interproscan import run_interproscan_ingest

    taxon_id = int(taxon_id_str)
    species_meta = SPECIES_REGISTRY.get(taxon_id_str, {})
    common_name = species_meta.get("common_name", taxon_id_str)

    logger.info("=== Domain ingest for %s (taxon %s) ===", common_name, taxon_id_str)

    if domain_source == "ftp":
        if not ftp_file:
            logger.error("--ftp-file required when --domain-source ftp")
            return
        run_ftp_domain_ingest(ftp_file, driver, [taxon_id])
        return

    if domain_source in ("uniprot", "both", "both_unreviewed"):
        run_uniprot_domain_ingest(taxon_id, driver)

    if domain_source in ("interpro",):
        # InterPro enrichment only (assumes UniProt already ran)
        enrich_existing_domains(taxon_id, driver)

    if domain_source in ("both", "both_unreviewed") and not skip_enrichment:
        enrich_existing_domains(taxon_id, driver)

    if domain_source == "interproscan" or (
        taxon_id in _LOW_COVERAGE and domain_source == "both_unreviewed"
    ):
        gtf_path = os.path.join(
            settings.gtf_data_dir,
            species_meta.get("gtf_filename", f"{taxon_id_str}.gtf.gz"),
        )
        fasta_path = os.path.join("data/genomes", f"{taxon_id}.fa.gz")
        run_interproscan_ingest(taxon_id, driver, gtf_path, fasta_path)


def print_coverage_report(driver) -> None:
    """Query Neo4j and print a domain coverage report for all loaded species."""
    query = """
    MATCH (s:Species)-[:HAS_GENE]->(g:Gene)
    OPTIONAL MATCH (g)-[:HAS_DOMAIN]->(d:Domain)
    WITH s.common_name AS species, s.taxon_id AS taxon,
         count(DISTINCT g) AS total_genes,
         count(DISTINCT CASE WHEN d IS NOT NULL THEN g END) AS genes_with_domains
    RETURN species, taxon, total_genes, genes_with_domains
    ORDER BY total_genes DESC
    """

    top_domain_query = """
    MATCH (s:Species {taxon_id: $taxon_id})-[:HAS_GENE]->(g:Gene)-[:HAS_DOMAIN]->(d:Domain)
    WHERE d.pfam_acc IS NOT NULL
    RETURN d.pfam_acc AS pfam_acc, d.name AS name, count(d) AS cnt
    ORDER BY cnt DESC
    LIMIT 1
    """

    WARN_THRESHOLD = 30.0
    ALERT_THRESHOLD = 10.0

    header = (
        f"  {'Species':<18} | {'Taxon':<8} | {'Genes':>6} | "
        f"{'With Domains':>12} | {'Coverage':>8} | Top Domain"
    )
    separator = "  " + "-" * 18 + "-+-" + "-" * 8 + "-+-" + "-" * 6 + "-+-" + "-" * 12 + "-+-" + "-" * 8 + "-+-" + "-" * 20

    print("\n=== Domain Coverage Report ===")
    print(header)
    print(separator)

    try:
        with driver.session() as session:
            rows = list(session.run(query))

        for row in rows:
            species = row["species"] or "Unknown"
            taxon = row["taxon"] or ""
            total = row["total_genes"] or 0
            with_domains = row["genes_with_domains"] or 0
            coverage = (with_domains / total * 100) if total > 0 else 0.0

            # Get top domain
            top_domain = "—"
            try:
                with driver.session() as session:
                    top = session.run(top_domain_query, taxon_id=taxon).single()
                    if top:
                        top_domain = f"{top['pfam_acc']} ({top['name'][:15] if top['name'] else '?'})"
            except Exception:
                pass

            # Colour coding via prefix
            prefix = "  "
            suffix = ""
            if coverage < ALERT_THRESHOLD:
                prefix = "⚠ "
                suffix = " [ALERT]"
            elif coverage < WARN_THRESHOLD:
                prefix = "! "
                suffix = " [WARN]"

            print(
                f"{prefix}{'%-18s' % species} | {'%-8s' % taxon} | {total:>6} | "
                f"{with_domains:>12} | {coverage:>7.1f}% | {top_domain}{suffix}"
            )

            if coverage < ALERT_THRESHOLD:
                print(
                    f"    → Consider running InterProScan for taxon {taxon}:\n"
                    f"      python -m app.ingestion.run_ingest --species {taxon} "
                    f"--domain-source interproscan"
                )
    except Exception as exc:
        logger.error("Coverage report error: %s", exc)
        print("  (Could not query Neo4j — is it running?)")

    print("")


def ingest_species(taxon_id: str, driver) -> None:
    species_meta = SPECIES_REGISTRY.get(taxon_id)
    if not species_meta:
        logger.error("Unknown taxon_id: %s", taxon_id)
        return

    gtf_path = os.path.join(settings.gtf_data_dir, species_meta["gtf_filename"])
    if not os.path.exists(gtf_path):
        logger.error("GTF file not found: %s", gtf_path)
        return

    logger.info("=== Ingesting %s (taxon %s) ===", species_meta["common_name"], taxon_id)

    # 1. Detect dialect
    dialect = detect_dialect(gtf_path)
    logger.info("Dialect: %s", dialect)

    # 2. Parse + extract
    records = parse_gtf_streaming(gtf_path, dialect)
    genes, transcripts, features = extract_features(records, taxon_id)

    # 3. Build neighborhood edges
    edges = build_neighborhood_edges(genes)
    logger.info("Built %d CO_LOCATED_WITH edges", len(edges))

    # 4. Domain annotations (BioMart if available; silently skip if file has server error)
    gene_domains: list = []
    biomart_used = False
    if species_meta["biomart_filename"]:
        biomart_path = os.path.join(settings.biomart_data_dir, species_meta["biomart_filename"])
        gene_domains = parse_biomart_tsv(biomart_path)
        if gene_domains:
            biomart_used = True
        elif os.path.exists(biomart_path):
            logger.warning(
                "BioMart file empty or invalid for taxon %s. "
                "Run domain ingestion separately: "
                "python -m app.ingestion.run_ingest --species %s --step domains",
                taxon_id, taxon_id,
            )
    elif dialect == "ncbi_gff3":
        # Extract domains from GFF3 Dbxref for E. coli
        records2 = parse_gtf_streaming(gtf_path, dialect)
        for rec in records2:
            if rec["feature_type"] == "gene":
                attrs = rec["attributes"]
                gene_id = attrs.get("gene_id", "")
                db_xrefs = attrs.get("db_xref", [])
                if gene_id and db_xrefs:
                    gene_domains.extend(
                        extract_domains_from_gff3_attrs(gene_id, db_xrefs)
                    )

    # 5. Write to Neo4j
    species_node = {
        "taxon_id":    taxon_id,
        "name":        species_meta["name"],
        "common_name": species_meta["common_name"],
        "assembly":    species_meta["assembly"],
        "kingdom":     species_meta["kingdom"],
        "gtf_source":  species_meta["gtf_source"],
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }

    with driver.session() as session:
        logger.info("Writing species node…")
        write_species_node(session, species_node)

        logger.info("Writing %d genes…", len(genes))
        write_genes_batch(session, genes)

        logger.info("Writing %d transcripts…", len(transcripts))
        write_transcripts_batch(session, transcripts)

        logger.info("Writing %d features…", len(features))
        write_features_batch(session, features)

        if gene_domains:
            logger.info("Writing %d domain associations…", len(gene_domains))
            write_domains_batch(session, gene_domains)

        logger.info("Writing %d neighborhood edges…", len(edges))
        write_edges_batch(session, edges)

    logger.info("=== Done: %s ===", species_meta["common_name"])


def _preflight_check(args) -> None:
    """
    Verify all data files needed for the requested run exist on disk.
    Prints a ✓/✗ table and exits non-zero if anything is missing.
    """
    targets = list(SPECIES_REGISTRY.keys()) if args.all else ([args.species] if args.species else [])
    if not targets:
        print("Specify --all or --species <taxon_id> to check.")
        sys.exit(1)

    domain_source = args.domain_source
    ftp_file      = getattr(args, "ftp_file", None)
    step          = getattr(args, "step", "all")

    missing: list[str] = []
    ok:      list[str] = []

    def _check(path: str, label: str) -> bool:
        if path and os.path.isfile(path) and os.path.getsize(path) > 0:
            size_mb = os.path.getsize(path) / 1_048_576
            ok.append(f"  ✓  {label:<45}  {size_mb:>8.1f} MB  {path}")
            return True
        elif path and os.path.isdir(path):
            missing.append(f"  ✗  {label:<45}  PATH IS A DIRECTORY  {path}")
            return False
        else:
            missing.append(f"  ✗  {label:<45}  MISSING      {path or '(not specified)'}")
            return False

    print(f"\nPre-flight check — {len(targets)} species  "
          f"step={step}  domain-source={domain_source or 'auto'}\n")

    # ── FTP file ──────────────────────────────────────────────────────────────
    if domain_source == "ftp" or step in ("domains", "all"):
        if domain_source == "ftp":
            _check(ftp_file, "protein2ipr.dat.gz  (FTP)")

    # ── Per-species files ─────────────────────────────────────────────────────
    for taxon_id in targets:
        meta = SPECIES_REGISTRY.get(taxon_id, {})
        name = meta.get("common_name", taxon_id)

        # GTF file
        if step in ("gtf", "all"):
            gtf_filename = meta.get("gtf_filename", "")
            gtf_path     = os.path.join(settings.gtf_data_dir, gtf_filename) if gtf_filename else ""
            _check(gtf_path, f"[{taxon_id:>6}] {name:<18} GTF")

        # Biomart TSV (used by GTF ingest step, not FTP domain ingest)
        if step in ("gtf", "all") and domain_source != "ftp":
            bm_filename = meta.get("biomart_filename") or ""
            bm_path     = os.path.join(settings.biomart_data_dir, bm_filename) if bm_filename else ""
            if bm_filename:
                _check(bm_path, f"[{taxon_id:>6}] {name:<18} biomart TSV")

        # When domain-source=ftp, biomart TSVs are OPTIONAL — FTP provides all
        # domain data so a missing biomart just means 0 initial domains during
        # GTF ingest, which is immediately corrected by the FTP pass.
        # Warn but don't fail.
        if step == "all" and domain_source == "ftp":
            bm_filename = meta.get("biomart_filename") or ""
            bm_path     = os.path.join(settings.biomart_data_dir, bm_filename) if bm_filename else ""
            if bm_filename and not (os.path.isfile(bm_path) and os.path.getsize(bm_path) > 0):
                ok.append(f"  ~  [{taxon_id:>6}] {name:<18} {'biomart TSV':<25}  OPTIONAL (FTP will cover domains)")

    # ── idmapping files (for species that use them) ───────────────────────────
    _TAXON_IDMAP_CODES = {
        "9606": "HUMAN_9606",   "10090": "MOUSE_10090", "7955": "DANRE_7955",
        "9031": "CHICK_9031",   "7227":  "DROME_7227",  "6239": "CAEEL_6239",
        "3702": "ARATH_3702",   "4932":  "YEAST_559292",
    }
    interpro_dir = os.environ.get("INTERPRO_DATA_DIR", "./data/interpro")
    for taxon_id in targets:
        code = _TAXON_IDMAP_CODES.get(taxon_id)
        if code:
            idmap_path = os.path.join(interpro_dir, f"{code}_idmapping.dat.gz")
            meta = SPECIES_REGISTRY.get(taxon_id, {})
            _check(idmap_path, f"[{taxon_id:>6}] {meta.get('common_name', taxon_id):<18} idmapping")

    # ── Print results ─────────────────────────────────────────────────────────
    if ok:
        print("Found:")
        print("\n".join(ok))
    if missing:
        print("\nMissing:")
        print("\n".join(missing))

    print(f"\n{'✓ All files present — ready to ingest.' if not missing else f'✗  {len(missing)} file(s) missing — resolve before running.'}")

    if missing:
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Gene-Intel ingestion pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # GTF ingestion
  python -m app.ingestion.run_ingest --species 9606
  python -m app.ingestion.run_ingest --all

  # Domain ingestion
  python -m app.ingestion.run_ingest --species 9606 --step domains
  python -m app.ingestion.run_ingest --species 9606 --domain-source uniprot
  python -m app.ingestion.run_ingest --species 175781 --domain-source interproscan

  # FTP bulk ingestion (requires download first)
  python -m app.ingestion.run_ingest --species 9606 --domain-source ftp \\
      --ftp-file data/interpro_ftp/protein2ipr.dat.gz

  # Coverage report
  python -m app.ingestion.run_ingest domains --report
        """,
    )

    # Positional command (optional — for 'domains --report')
    parser.add_argument(
        "command", nargs="?", default=None,
        help="Sub-command: 'domains' (use with --report)",
    )

    species_group = parser.add_mutually_exclusive_group()
    species_group.add_argument("--species", help="Taxon ID to ingest (e.g. 9606)")
    species_group.add_argument("--all", action="store_true", help="Ingest all 17 species")

    parser.add_argument(
        "--step", choices=["gtf", "domains", "all"], default="all",
        help="Which ingestion step to run (default: all)",
    )
    parser.add_argument(
        "--domain-source",
        choices=["uniprot", "interpro", "interproscan", "ftp", "both"],
        default=None,
        help="Domain data source (default: auto-selected per species)",
    )
    parser.add_argument(
        "--skip-domain-enrichment", action="store_true",
        help="Skip InterPro enrichment step (faster re-runs)",
    )
    parser.add_argument(
        "--ftp-file", default=None,
        help="Path to protein2ipr.dat.gz for FTP ingestion",
    )
    parser.add_argument(
        "--report", action="store_true",
        help="Print domain coverage report (use with 'domains' command)",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Dry-run pre-flight check: verify all data files exist without ingesting anything",
    )

    args = parser.parse_args()

    # Handle: --check (pre-flight file existence check)
    if args.check:
        _preflight_check(args)
        return

    # Handle: python -m ... domains --report
    if args.command == "domains" and args.report:
        driver = get_driver()
        print_coverage_report(driver)
        driver.close()
        return

    # For GTF/domain ingestion, need at least --species or --all
    if not args.all and not args.species:
        parser.print_help()
        sys.exit(0)

    driver = get_driver()

    logger.info("Initialising Neo4j schema…")
    init_schema(driver)

    taxon_ids = list(SPECIES_REGISTRY.keys()) if args.all else [args.species]

    for taxon_id in taxon_ids:
        if args.step in ("gtf", "all"):
            ingest_species(taxon_id, driver)

    # FTP ingest: single pass over the file for ALL species at once.
    # Running it per-species would scan 1B+ lines once per taxon (~30 min each).
    if args.step in ("domains", "all"):
        ftp_taxon_ids = []
        non_ftp_taxon_ids = []
        for taxon_id in taxon_ids:
            source = args.domain_source
            if source is None:
                source = _auto_select_domain_route(int(taxon_id))
            if source == "ftp":
                ftp_taxon_ids.append(taxon_id)
            else:
                non_ftp_taxon_ids.append(taxon_id)

        if ftp_taxon_ids:
            if not args.ftp_file:
                logger.error("--ftp-file required when --domain-source ftp")
            else:
                from app.ingestion.domain_ingest_ftp import run_ftp_domain_ingest
                logger.info(
                    "FTP domain ingest: single pass for %d species: %s",
                    len(ftp_taxon_ids), ftp_taxon_ids,
                )
                run_ftp_domain_ingest(
                    args.ftp_file, driver,
                    [int(t) for t in ftp_taxon_ids],
                )

        for taxon_id in non_ftp_taxon_ids:
            source = args.domain_source
            if source is None:
                source = _auto_select_domain_route(int(taxon_id))
            run_domain_ingest(
                taxon_id,
                driver,
                domain_source=source,
                skip_enrichment=args.skip_domain_enrichment,
                ftp_file=args.ftp_file,
            )

    driver.close()


if __name__ == "__main__":
    main()
