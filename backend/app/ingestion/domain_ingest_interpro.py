"""
InterPro REST API domain enrichment — Route 1 (enrichment + fallback).

Adds e-values and cross-database IDs to existing Domain nodes loaded by the
UniProt route. Also serves as a fallback for species with poor UniProt coverage.

Rate limit note (InterPro 2025):
  - Maximum 1 request per 0.5 seconds (enforced below)
  - User-Agent: "Gene-Intel/2.0 (research; contact: <CONTACT_EMAIL>)"
  - Backoff: 5s on 429, 30s on 503

Connected to:
  - run_ingest.py: called after domain_ingest_uniprot completes
  - domain_ingest_uniprot.py: enriches Domain nodes created there
"""

from __future__ import annotations

import logging
import os
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.ebi.ac.uk/interpro/api"
_RATE_LIMIT_DELAY = float(os.getenv("INTERPRO_RATE_LIMIT_DELAY", "0.5"))
_CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "gene-intel@example.com")

# Same remap as domain_ingest_uniprot — strain-level IDs required by the API
_TAXON_REMAP = {
    4932: 559292,   # S. cerevisiae species → S288C reference strain
}

_HEADERS = {
    "Accept": "application/json",
    "User-Agent": f"Gene-Intel/2.0 (research; contact: {_CONTACT_EMAIL})",
}

# Simple in-memory LRU cache for on-demand protein lookups
_protein_cache: OrderedDict[str, tuple[list[dict], datetime]] = OrderedDict()
_CACHE_MAX_SIZE = 10_000
_CACHE_TTL_HOURS = 1


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_with_rate_limit(url: str, params: dict | None = None) -> requests.Response:
    """GET with enforced rate limit and retry on 429/503."""
    time.sleep(_RATE_LIMIT_DELAY)

    resp = requests.get(url, params=params, headers=_HEADERS, timeout=30)

    if resp.status_code == 429:
        logger.warning("InterPro rate-limited (429). Waiting 5s…")
        time.sleep(5)
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=30)

    if resp.status_code == 503:
        logger.warning("InterPro 503. Waiting 30s…")
        time.sleep(30)
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=30)

    return resp


def _parse_domain_from_result(result: dict) -> list[dict[str, Any]]:
    """
    Extract domain dicts from a single result of the protein-centric endpoint:
      /protein/uniprot/entry/pfam/{pfam_acc}/taxonomy/uniprot/{taxon_id}

    Response shape per result:
      metadata.accession              → UniProt protein accession
      entries[].accession             → Pfam accession (PFxxxxx)
      entries[].entry_protein_locations[].score     → e-value
      entries[].entry_protein_locations[].fragments[].start/end → coordinates
    """
    domains = []
    try:
        protein_acc = result["metadata"]["accession"]
        for entry in result.get("entries", []):
            pfam_acc = entry.get("accession", "")
            if not pfam_acc.upper().startswith("PF"):
                continue

            for location in entry.get("entry_protein_locations", []):
                score = location.get("score")  # e-value at location level
                for fragment in location.get("fragments", []):
                    start = fragment.get("start")
                    end = fragment.get("end")
                    if start is None or end is None:
                        continue
                    domains.append({
                        "uniprot_acc": protein_acc,
                        "pfam_acc":    pfam_acc.upper(),
                        "domain_name": "",
                        "start_aa":    int(start),
                        "end_aa":      int(end),
                        "e_value":     score,
                        "source_db":   "pfam_interpro",
                    })
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("Skipping malformed InterPro result: %s", exc)
    return domains


# ─────────────────────────────────────────────────────────────────────────────
# fetch_interpro_domains_for_taxon
# ─────────────────────────────────────────────────────────────────────────────

def fetch_interpro_domains_for_pfam(
    pfam_acc: str,
    taxon_id: int,
    page_size: int = 200,
) -> list[dict[str, Any]]:
    """
    Fetch all protein-domain records for one Pfam entry within a taxon.

    Endpoint (protein-centric, returns inline entries + positions):
        /protein/uniprot/entry/pfam/{pfam_acc}/taxonomy/uniprot/{api_taxon}
    """
    api_taxon = _TAXON_REMAP.get(taxon_id, taxon_id)
    url = f"{_BASE_URL}/protein/uniprot/entry/pfam/{pfam_acc}/taxonomy/uniprot/{api_taxon}"
    params: dict[str, Any] = {"page_size": page_size}

    domains: list[dict[str, Any]] = []
    page_num = 0

    while url:
        page_num += 1
        resp = _get_with_rate_limit(url, params if page_num == 1 else None)

        if resp.status_code == 404:
            break  # This Pfam entry has no proteins for this taxon — normal
        if resp.status_code != 200:
            logger.warning(
                "InterPro HTTP %d for %s / taxon %d page %d",
                resp.status_code, pfam_acc, taxon_id, page_num,
            )
            break

        data = resp.json()
        for result in data.get("results", []):
            domains.extend(_parse_domain_from_result(result))

        url = data.get("next")
        params = {}

    return domains


def fetch_interpro_domains_for_taxon(
    taxon_id: int,
    pfam_accs: list[str],
    page_size: int = 200,
) -> list[dict[str, Any]]:
    """
    Fetch Pfam domain matches from InterPro for a list of Pfam accessions.

    Iterates one API call per Pfam accession using the protein-centric endpoint
    that returns inline entry_protein_locations (positions + e-values).

    Args:
        taxon_id:   NCBI taxonomy ID.
        pfam_accs:  Pfam accessions to query (typically taken from existing
                    Domain nodes in Neo4j so only relevant entries are fetched).
        page_size:  Results per page.

    Returns:
        list of domain dicts with pfam_acc, start_aa, end_aa, e_value.
    """
    all_domains: list[dict[str, Any]] = []
    total_pages = 0

    for pfam_acc in pfam_accs:
        domains = fetch_interpro_domains_for_pfam(pfam_acc, taxon_id, page_size)
        all_domains.extend(domains)
        total_pages += 1

    logger.info(
        "InterPro fetch for taxon %d: %d domains across %d Pfam entries",
        taxon_id, len(all_domains), total_pages,
    )
    return all_domains


# ─────────────────────────────────────────────────────────────────────────────
# enrich_existing_domains
# ─────────────────────────────────────────────────────────────────────────────

def enrich_existing_domains(taxon_id: int, driver) -> dict[str, int]:
    """
    Enrich Domain nodes (loaded by UniProt route) with e-values from InterPro.
    Only updates Domain nodes where e_value IS NULL — does not create new nodes.

    Queries Neo4j first to find which Pfam accessions actually need enrichment,
    then fetches only those entries from InterPro (one API call per Pfam entry).

    Returns:
        dict with keys: enriched, not_found
    """
    logger.info("Starting InterPro domain enrichment for taxon %d", taxon_id)

    # Find only the Pfam accessions present in Domain nodes that need enrichment
    pfam_query = """
    MATCH (d:Domain)<-[:HAS_DOMAIN]-(:Gene {species_taxon: $taxon_id})
    WHERE d.e_value IS NULL AND d.pfam_acc IS NOT NULL
    RETURN DISTINCT d.pfam_acc AS pfam_acc
    """
    with driver.session() as session:
        pfam_accs = [r["pfam_acc"] for r in session.run(pfam_query, taxon_id=str(taxon_id))]

    if not pfam_accs:
        logger.info("No Domain nodes needing e-value enrichment for taxon %d", taxon_id)
        return {"enriched": 0, "not_found": 0}

    logger.info("Fetching InterPro e-values for %d distinct Pfam entries", len(pfam_accs))
    domains = fetch_interpro_domains_for_taxon(taxon_id, pfam_accs)

    if not domains:
        logger.warning("No InterPro domains found for taxon %d", taxon_id)
        return {"enriched": 0, "not_found": 0}

    query = """
    UNWIND $batch AS row
    MATCH (d:Domain {pfam_acc: row.pfam_acc, start_aa: row.start_aa})
          <-[:HAS_DOMAIN]-(:Gene {species_taxon: $taxon_id})
    WHERE d.e_value IS NULL
    SET d.e_value = row.e_value, d.source_db = row.source_db
    RETURN count(d) AS updated
    """

    enriched = 0
    not_found = 0
    batch_size = 500

    def _chunks(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    for chunk in _chunks(domains, batch_size):
        batch_rows = [
            {
                "pfam_acc":  d["pfam_acc"],
                "start_aa":  d["start_aa"],
                "e_value":   d["e_value"],
                "source_db": d["source_db"],
            }
            for d in chunk
        ]
        try:
            with driver.session() as session:
                result = session.run(query, batch=batch_rows, taxon_id=str(taxon_id))
                summary = result.consume()
                enriched += summary.counters.properties_set
        except Exception as exc:
            logger.error("Enrichment batch error: %s", exc)

    logger.info("Taxon %d enrichment: %d properties set", taxon_id, enriched)
    return {"enriched": enriched, "not_found": not_found}


# ─────────────────────────────────────────────────────────────────────────────
# fetch_interpro_at_query_time (on-demand single-protein lookup)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_interpro_at_query_time(
    gene_id: str,
    uniprot_acc: str,
) -> list[dict[str, Any]]:
    """
    Fetch domain annotations for a single protein on-demand (query time).

    Used by /api/gene/{gene_id} when Domain nodes have no e_value.
    Results are cached for 1 hour (max 10,000 entries, LRU eviction).

    Returns a list of domain dicts for that single protein.
    """
    now = datetime.utcnow()

    # Check cache
    if uniprot_acc in _protein_cache:
        cached_domains, cached_at = _protein_cache[uniprot_acc]
        if now - cached_at < timedelta(hours=_CACHE_TTL_HOURS):
            # Move to end (LRU refresh)
            _protein_cache.move_to_end(uniprot_acc)
            return cached_domains
        else:
            del _protein_cache[uniprot_acc]

    url = f"{_BASE_URL}/protein/uniprot/{uniprot_acc}"
    params = {"extra_fields": "sequence"}

    try:
        resp = _get_with_rate_limit(url, params)
        if resp.status_code != 200:
            logger.warning(
                "InterPro on-demand lookup failed for %s: HTTP %d",
                uniprot_acc, resp.status_code,
            )
            return []

        data = resp.json()
        # Wrap in list to reuse _parse_domain_from_result
        results = data if isinstance(data, list) else [data]
        all_domains: list[dict[str, Any]] = []
        for result in results:
            all_domains.extend(_parse_domain_from_result(result))

    except Exception as exc:
        logger.warning("InterPro on-demand error for %s: %s", uniprot_acc, exc)
        return []

    # Evict oldest entry if at capacity
    if len(_protein_cache) >= _CACHE_MAX_SIZE:
        _protein_cache.popitem(last=False)

    _protein_cache[uniprot_acc] = (all_domains, now)
    return all_domains
