"""
FTP bulk domain ingestion — Route 3 (offline/production).

Downloads and streams the InterPro protein2ipr.dat.gz file (5-7GB compressed)
and loads domain annotations for all 17 species into Neo4j.

File format (tab-separated, no header):
    Col 0: UniProt accession  (e.g. P31946)
    Col 1: InterPro accession (e.g. IPR000253)
    Col 2: InterPro name      (e.g. 14-3-3 protein)
    Col 3: Member DB sig      (e.g. PF00244)   ← only keep rows starting with PF
    Col 4: Member DB name     (e.g. 14-3-3)
    Col 5: Start position aa  (e.g. 5)
    Col 6: End position aa    (e.g. 247)

Estimated runtime: 30-90 minutes depending on disk speed.

Connected to:
  - run_ingest.py: called with --domain-source ftp
  - scripts/download_interpro_ftp.sh: downloads the FTP file first
"""

from __future__ import annotations

import gzip
import logging
import time
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)

_FTP_URL = "https://ftp.ebi.ac.uk/pub/databases/interpro/current_release/protein2ipr.dat.gz"
_FLUSH_EVERY = 10_000  # Neo4j write frequency
_LOG_EVERY_LINES = 10_000_000


# ─────────────────────────────────────────────────────────────────────────────
# build_taxon_uniprot_map
# ─────────────────────────────────────────────────────────────────────────────

def build_taxon_uniprot_map(
    driver,
    taxon_ids: list[int],
) -> tuple[dict[str, dict], set[str]]:
    """
    Build a mapping of UniProt accession → (gene_id, taxon_id) from Neo4j.

    Returns:
        (mapping_dict, acc_set) where:
            mapping_dict: {uniprot_acc: {"gene_id": ..., "taxon_id": ...}}
            acc_set:      set of all uniprot_accs for O(1) membership tests
    """
    query = """
    MATCH (g:Gene)
    WHERE g.uniprot_acc IS NOT NULL
      AND g.species_taxon IN $taxon_ids
    RETURN g.uniprot_acc AS uniprot_acc, g.gene_id AS gene_id,
           g.species_taxon AS taxon_id
    """

    mapping: dict[str, dict] = {}

    try:
        with driver.session() as session:
            result = session.run(query, taxon_ids=[str(t) for t in taxon_ids])
            for record in result:
                acc = record["uniprot_acc"]
                mapping[acc] = {
                    "gene_id":  record["gene_id"],
                    "taxon_id": record["taxon_id"],
                }
    except Exception as exc:
        logger.error("Failed to build UniProt map from Neo4j: %s", exc)

    logger.info("Loaded %d UniProt accessions from Neo4j for filtering", len(mapping))
    acc_set = set(mapping.keys())
    return mapping, acc_set


# ─────────────────────────────────────────────────────────────────────────────
# stream_parse_protein2ipr
# ─────────────────────────────────────────────────────────────────────────────

def stream_parse_protein2ipr(
    filepath: str,
    uniprot_filter_set: set[str],
):
    """
    Streaming parser for the protein2ipr.dat.gz file.
    Yields one dict per relevant Pfam domain match.

    Args:
        filepath:           Path to protein2ipr.dat.gz
        uniprot_filter_set: Set of UniProt accessions to keep

    Yields:
        {uniprot_acc, ipr_acc, ipr_name, pfam_acc, domain_name, start_aa, end_aa,
         e_value, source_db}
    """
    t0 = time.monotonic()
    line_count = 0
    domain_count = 0
    skip_count = 0

    opener = gzip.open if filepath.endswith(".gz") else open

    with opener(filepath, "rt", encoding="utf-8") as f:
        for raw_line in f:
            line_count += 1

            if line_count % _LOG_EVERY_LINES == 0:
                elapsed = time.monotonic() - t0
                logger.info(
                    "Parsed %dM lines, found %d matching domains so far… (%.0fs elapsed)",
                    line_count // 1_000_000, domain_count, elapsed,
                )

            line = raw_line.rstrip()
            if not line:
                continue

            cols = line.split("\t")
            if len(cols) < 7:
                logger.warning(
                    "Malformed line %d (expected 7+ cols, got %d) — skipped",
                    line_count, len(cols),
                )
                skip_count += 1
                continue

            uniprot_acc = cols[0]

            # Fast filter: only keep our species
            if uniprot_acc not in uniprot_filter_set:
                continue

            pfam_acc = cols[3]
            # Only keep Pfam entries
            if not pfam_acc.startswith("PF"):
                continue

            try:
                start_aa = int(cols[5])
                end_aa = int(cols[6])
            except (ValueError, IndexError):
                logger.warning("Malformed start/end on line %d — skipped", line_count)
                skip_count += 1
                continue

            domain_count += 1
            yield {
                "uniprot_acc": uniprot_acc,
                "ipr_acc":     cols[1],
                "ipr_name":    cols[2],
                "pfam_acc":    pfam_acc,
                "domain_name": cols[4],
                "start_aa":    start_aa,
                "end_aa":      end_aa,
                "e_value":     None,
                "source_db":   "interpro_ftp",
            }

    elapsed = time.monotonic() - t0
    logger.info(
        "Parsing complete: %d lines scanned, %d domains matched, "
        "%d malformed lines skipped, %.0f seconds",
        line_count, domain_count, skip_count, elapsed,
    )


# ─────────────────────────────────────────────────────────────────────────────
# run_ftp_domain_ingest
# ─────────────────────────────────────────────────────────────────────────────

def run_ftp_domain_ingest(
    ftp_filepath: str,
    driver,
    taxon_ids: list[int],
) -> dict[str, Any]:
    """
    Full FTP-based ingestion pipeline for all 17 species.

    Note: This is designed for overnight runs.
    Estimated time: 30-90 minutes depending on disk speed and Neo4j write rate.

    Steps:
        1. Build UniProt → gene_id filter map from Neo4j.
        2. Stream-parse protein2ipr.dat.gz (slow step).
        3. Flush to Neo4j every 10,000 records.
        4. Return stats per species.

    Args:
        ftp_filepath: Path to downloaded protein2ipr.dat.gz
        driver:       Neo4j driver instance
        taxon_ids:    List of taxon IDs to ingest (filter from FTP data)
    """
    logger.info("Starting FTP domain ingest from: %s", ftp_filepath)
    logger.info("Species: %s", taxon_ids)

    # Step 1: Build filter map
    uniprot_map, acc_set = build_taxon_uniprot_map(driver, taxon_ids)

    if not acc_set:
        logger.warning(
            "No UniProt accessions found in Neo4j for taxon_ids %s. "
            "Make sure GTF data is loaded first.",
            taxon_ids,
        )

    # Step 2: Stream parse + batch write
    buffer: list[dict] = []
    per_taxon_counts: dict[str, int] = defaultdict(int)
    total_loaded = 0
    total_skipped = 0

    write_query = """
    UNWIND $batch AS row
    MATCH (g:Gene {gene_id: row.gene_id})
    MERGE (d:Domain {domain_id: row.domain_id})
    ON CREATE SET d += row.props
    ON MATCH  SET d += row.props
    MERGE (g)-[:HAS_DOMAIN]->(d)
    """

    def _flush(buf: list[dict]):
        nonlocal total_loaded
        batch_rows = []
        for item in buf:
            gene_info = uniprot_map.get(item["uniprot_acc"])
            if not gene_info:
                continue
            gene_id = gene_info["gene_id"]
            taxon_id = gene_info["taxon_id"]
            domain_id = f"{gene_id}__{item['pfam_acc']}__{item['start_aa']}"
            props = {
                "domain_id":    domain_id,
                "pfam_acc":     item["pfam_acc"],
                "name":         item["domain_name"],
                "ipr_acc":      item["ipr_acc"],
                "ipr_name":     item["ipr_name"],
                "source_db":    item["source_db"],
                "start_aa":     item["start_aa"],
                "end_aa":       item["end_aa"],
                "e_value":      item.get("e_value"),
                "species_taxon": taxon_id,
            }
            batch_rows.append({"gene_id": gene_id, "domain_id": domain_id, "props": props})
            per_taxon_counts[str(taxon_id)] += 1

        if not batch_rows:
            return

        try:
            with driver.session() as session:
                session.run(write_query, batch=batch_rows)
            total_loaded += len(batch_rows)
        except Exception as exc:
            logger.error("FTP batch write error: %s", exc)

    for domain in stream_parse_protein2ipr(ftp_filepath, acc_set):
        buffer.append(domain)
        if len(buffer) >= _FLUSH_EVERY:
            _flush(buffer)
            buffer.clear()

    # Flush remaining
    if buffer:
        _flush(buffer)

    logger.info(
        "FTP ingest complete: %d domains loaded, %d skipped",
        total_loaded, total_skipped,
    )
    logger.info("Per-taxon counts: %s", dict(per_taxon_counts))

    return {
        "total_loaded": total_loaded,
        "per_taxon": dict(per_taxon_counts),
    }
