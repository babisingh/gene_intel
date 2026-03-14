"""
CLI entrypoint for the Gene-Intel ingestion pipeline.

Usage:
    python -m app.ingestion.run_ingest --species 9606
    python -m app.ingestion.run_ingest --species 511145   # E. coli (GFF3 auto-detected)
    python -m app.ingestion.run_ingest --all              # All 15 species

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
}


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

    # 4. Domain annotations
    gene_domains: list = []
    if species_meta["biomart_filename"]:
        biomart_path = os.path.join(settings.biomart_data_dir, species_meta["biomart_filename"])
        gene_domains = parse_biomart_tsv(biomart_path)
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


def main():
    parser = argparse.ArgumentParser(description="Gene-Intel ingestion pipeline")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--species", help="Taxon ID to ingest (e.g. 9606)")
    group.add_argument("--all", action="store_true", help="Ingest all 15 species")
    args = parser.parse_args()

    driver = get_driver()

    logger.info("Initialising Neo4j schema…")
    init_schema(driver)

    if args.all:
        for taxon_id in SPECIES_REGISTRY:
            ingest_species(taxon_id, driver)
    else:
        ingest_species(args.species, driver)

    driver.close()


if __name__ == "__main__":
    main()
