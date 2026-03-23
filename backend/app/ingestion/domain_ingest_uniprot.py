"""
UniProt REST API domain ingestion — primary route.

Fetches protein domain annotations from the UniProt REST API and loads them
into Neo4j as Domain nodes linked to Gene nodes via HAS_DOMAIN relationships.

Domain schema in Neo4j:
    (Gene)-[:HAS_DOMAIN]->(Domain)
    Domain properties: {
        domain_id:     "<gene_id>__<pfam_acc>__<start>",
        pfam_acc:      "PF00069",
        name:          "Protein kinase",
        source_db:     "pfam",
        start_aa:      123,
        end_aa:        380,
        e_value:       None,   # enriched by InterPro route
        species_taxon: 9606,
    }

Connected to:
  - run_ingest.py: calls run_uniprot_domain_ingest()
  - domain_ingest_interpro.py: enriches e_value after this route runs
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://rest.uniprot.org/uniprotkb/search"
_PAGE_SIZE = 500

# Species that have good Swiss-Prot (reviewed) coverage
_REVIEWED_ONLY_TAXONS = {
    9606, 10090, 7955, 9031, 9598, 7227, 6239,
    3702, 4530, 4932, 9913, 8665,
}

# Some species use a strain-level taxon in UniProt/InterPro that differs from
# the NCBI species-level ID used by Ensembl GTF files.
_TAXON_REMAP = {
    4932: 559292,   # S. cerevisiae species → S288C reference strain
}


# ─────────────────────────────────────────────────────────────────────────────
# Fetch
# ─────────────────────────────────────────────────────────────────────────────

def fetch_uniprot_domains(
    taxon_id: int,
    reviewed_only: bool = True,
    max_pages: int | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch all domain feature annotations for a given species from UniProt.

    Args:
        taxon_id:      NCBI taxonomy ID (e.g. 9606 for human).
        reviewed_only: If True, only fetch Swiss-Prot reviewed entries.
        max_pages:     Limit number of pages (for testing; None = unlimited).

    Returns:
        list of dicts with keys:
            uniprot_acc, gene_name, pfam_acc, domain_name,
            start_aa, end_aa, e_value (always None from this route)
    """
    api_taxon = _TAXON_REMAP.get(taxon_id, taxon_id)
    if reviewed_only:
        query = f"(taxonomy_id:{api_taxon} AND reviewed:true AND ft_domain:*)"
    else:
        query = f"(taxonomy_id:{api_taxon} AND ft_domain:*)"

    params: dict[str, Any] = {
        "query": query,
        "fields": "accession,gene_names,ft_domain,xref_pfam",
        "format": "json",
        "size": _PAGE_SIZE,
    }

    domains: list[dict[str, Any]] = []
    page_num = 0
    url: str | None = _BASE_URL

    while url:
        page_num += 1
        if max_pages is not None and page_num > max_pages:
            break

        try:
            if page_num == 1:
                resp = requests.get(url, params=params, timeout=30)
            else:
                resp = requests.get(url, timeout=30)
        except requests.exceptions.RequestException as exc:
            logger.error("UniProt request error (page %d): %s", page_num, exc)
            break

        if resp.status_code == 429:
            wait = 5
            for attempt in range(3):
                logger.warning("UniProt rate-limited (429). Waiting %ds…", wait)
                time.sleep(wait)
                if page_num == 1:
                    resp = requests.get(url, params=params, timeout=30)
                else:
                    resp = requests.get(url, timeout=30)
                if resp.status_code != 429:
                    break
                wait *= 2
            if resp.status_code == 429:
                logger.error("UniProt rate limit not resolved after retries — aborting page %d", page_num)
                break

        if resp.status_code == 503:
            logger.warning("UniProt 503 — waiting 30s then retrying once…")
            time.sleep(30)
            if page_num == 1:
                resp = requests.get(url, params=params, timeout=30)
            else:
                resp = requests.get(url, timeout=30)

        if resp.status_code != 200:
            logger.error("UniProt HTTP %d on page %d", resp.status_code, page_num)
            break

        data = resp.json()
        protein_list = data.get("results", [])
        logger.info("Page %d: %d proteins", page_num, len(protein_list))

        for protein in protein_list:
            acc = protein.get("primaryAccession", "")
            # Gene name: first primary gene name, or accession as fallback
            gene_names_section = protein.get("genes", [])
            gene_name = acc
            if gene_names_section:
                primary = gene_names_section[0].get("geneName", {})
                gene_name = primary.get("value", acc)

            # Pfam accessions are at the protein level in uniProtKBCrossReferences,
            # not inside individual feature entries.
            pfam_list = [
                x["id"]
                for x in protein.get("uniProtKBCrossReferences", [])
                if x.get("database") == "Pfam"
            ]

            domain_features = [
                f for f in protein.get("features", [])
                if f.get("type") == "Domain"
            ]

            for idx, feat in enumerate(domain_features):
                domain_name = feat.get("description", "")
                location = feat.get("location", {})
                start_aa = location.get("start", {}).get("value")
                end_aa = location.get("end", {}).get("value")

                if start_aa is None or end_aa is None:
                    continue

                # Pair Pfam accessions with domain features by index when counts
                # match exactly; fall back to first Pfam when only one is listed.
                if len(pfam_list) == len(domain_features):
                    pfam_acc = pfam_list[idx]
                elif len(pfam_list) == 1:
                    pfam_acc = pfam_list[0]
                else:
                    pfam_acc = None

                domain_id = (
                    f"{gene_name}__{pfam_acc}__{start_aa}"
                    if pfam_acc
                    else f"{gene_name}__{domain_name.replace(' ', '_')}__{start_aa}"
                )

                domains.append({
                    "uniprot_acc":  acc,
                    "gene_name":    gene_name,
                    "pfam_acc":     pfam_acc,
                    "domain_name":  domain_name,
                    "domain_id":    domain_id,
                    "start_aa":     int(start_aa),
                    "end_aa":       int(end_aa),
                    "e_value":      None,
                    "source_db":    "uniprot",
                    "species_taxon": str(taxon_id),  # Gene nodes store this as str
                })

        # Pagination: follow Link: <url>; rel="next"
        link_header = resp.headers.get("Link", "")
        url = _parse_next_link(link_header)

        if url:
            time.sleep(0.3)  # polite delay between pages

    logger.info("Total domains extracted for taxon %d: %d", taxon_id, len(domains))
    return domains


def _parse_next_link(link_header: str) -> str | None:
    """Parse the Link header and return the 'next' URL or None."""
    if not link_header:
        return None
    for part in link_header.split(","):
        part = part.strip()
        if 'rel="next"' in part:
            url_part = part.split(";")[0].strip()
            if url_part.startswith("<") and url_part.endswith(">"):
                return url_part[1:-1]
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Load to Neo4j
# ─────────────────────────────────────────────────────────────────────────────

def load_domains_to_neo4j(
    domains: list[dict[str, Any]],
    driver,
    batch_size: int = 500,
) -> dict[str, int]:
    """
    Load domain records into Neo4j using batch MERGE operations.

    Args:
        domains:    Output of fetch_uniprot_domains().
        driver:     Neo4j driver instance.
        batch_size: Number of records per Cypher batch.

    Returns:
        dict with keys: loaded, skipped_no_gene, errors
    """
    query = """
    UNWIND $batch AS row
    MATCH (g:Gene {name: row.gene_name, species_taxon: row.species_taxon})
    MERGE (d:Domain {domain_id: row.domain_id})
    ON CREATE SET d += row.props
    ON MATCH  SET d += row.props
    MERGE (g)-[:HAS_DOMAIN]->(d)
    RETURN count(g) AS matched
    """

    loaded = 0
    skipped_no_gene = 0
    errors = 0

    def _chunks(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    for chunk in _chunks(domains, batch_size):
        batch_rows = []
        for d in chunk:
            props = {
                "domain_id":    d["domain_id"],
                "uniprot_acc":  d["uniprot_acc"],
                "pfam_acc":     d["pfam_acc"],
                "name":         d["domain_name"],
                "source_db":    d["source_db"],
                "start_aa":     d["start_aa"],
                "end_aa":       d["end_aa"],
                "e_value":      d.get("e_value"),
                "species_taxon": d["species_taxon"],
            }
            batch_rows.append({
                "gene_name":    d["gene_name"],
                "species_taxon": d["species_taxon"],
                "domain_id":    d["domain_id"],
                "props":        props,
            })

        try:
            with driver.session() as session:
                session.run(query, batch=batch_rows)
                loaded += len(chunk)
        except Exception as exc:
            logger.error("Batch write error: %s", exc)
            errors += len(chunk)

    # NOTE: Accurate skipped_no_gene count requires a two-pass approach.
    # For now, report totals conservatively.
    return {"loaded": loaded, "skipped_no_gene": skipped_no_gene, "errors": errors}


def load_domains_to_neo4j_accurate(
    domains: list[dict[str, Any]],
    driver,
    batch_size: int = 500,
) -> dict[str, int]:
    """
    Accurate version that tracks which genes were not found.
    Uses OPTIONAL MATCH to detect missing genes.
    """
    query = """
    UNWIND $batch AS row
    OPTIONAL MATCH (g:Gene {name: row.gene_name, species_taxon: row.species_taxon})
    WITH g, row
    WHERE g IS NOT NULL
    MERGE (d:Domain {domain_id: row.domain_id})
    ON CREATE SET d += row.props
    ON MATCH  SET d += row.props
    MERGE (g)-[:HAS_DOMAIN]->(d)
    """

    check_query = """
    UNWIND $batch AS row
    OPTIONAL MATCH (g:Gene {name: row.gene_name, species_taxon: row.species_taxon})
    RETURN row.gene_name AS gene_name, g IS NOT NULL AS found
    """

    loaded = 0
    skipped_no_gene = 0
    errors = 0

    def _chunks(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    for chunk in _chunks(domains, batch_size):
        batch_rows = []
        for d in chunk:
            props = {
                "domain_id":    d["domain_id"],
                "uniprot_acc":  d["uniprot_acc"],
                "pfam_acc":     d["pfam_acc"],
                "name":         d["domain_name"],
                "source_db":    d["source_db"],
                "start_aa":     d["start_aa"],
                "end_aa":       d["end_aa"],
                "e_value":      d.get("e_value"),
                "species_taxon": d["species_taxon"],
            }
            batch_rows.append({
                "gene_name":    d["gene_name"],
                "species_taxon": d["species_taxon"],
                "domain_id":    d["domain_id"],
                "props":        props,
            })

        try:
            with driver.session() as session:
                # Check which genes exist
                check_result = session.run(check_query, batch=batch_rows)
                gene_found = {r["gene_name"]: r["found"] for r in check_result}
                batch_skipped = sum(1 for f in gene_found.values() if not f)
                batch_found = len(gene_found) - batch_skipped

                if batch_found > 0:
                    session.run(query, batch=batch_rows)

                loaded += batch_found
                skipped_no_gene += batch_skipped

                for gene_name, found in gene_found.items():
                    if not found:
                        logger.debug(
                            "Gene not found in Neo4j: %s (taxon %d) — skipped",
                            gene_name,
                            chunk[0]["species_taxon"] if chunk else 0,
                        )
        except Exception as exc:
            logger.error("Batch write error: %s", exc)
            errors += len(chunk)

    return {"loaded": loaded, "skipped_no_gene": skipped_no_gene, "errors": errors}


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────────────────────

def run_uniprot_domain_ingest(taxon_id: int, driver) -> dict[str, Any]:
    """
    Orchestrator: fetch + load UniProt domains for one species.

    Steps:
        1. Try reviewed_only=True first (Swiss-Prot).
        2. If result count < 100, retry with reviewed_only=False (TrEMBL).
        3. Load to Neo4j.
        4. Return stats dict.
    """
    logger.info("Starting UniProt domain ingest for taxon %d", taxon_id)

    reviewed_only = taxon_id in _REVIEWED_ONLY_TAXONS
    domains = fetch_uniprot_domains(taxon_id, reviewed_only=reviewed_only)

    if len(domains) < 100 and reviewed_only:
        logger.warning(
            "Low Swiss-Prot coverage for taxon %d (%d domains), "
            "falling back to TrEMBL (unreviewed)",
            taxon_id, len(domains),
        )
        domains = fetch_uniprot_domains(taxon_id, reviewed_only=False)

    stats = load_domains_to_neo4j_accurate(domains, driver)

    logger.info(
        "Taxon %d: loaded %d domains, skipped %d (gene not found), errors %d",
        taxon_id, stats["loaded"], stats["skipped_no_gene"], stats["errors"],
    )
    return {"taxon_id": taxon_id, **stats}
