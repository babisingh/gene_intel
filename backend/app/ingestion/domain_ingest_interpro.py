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
    """Extract domain dicts from a single InterPro API result entry."""
    domains = []
    try:
        protein_acc = result["metadata"]["accession"]
        entries = result.get("entries", [])
        for entry in entries:
            meta = entry.get("metadata", {})
            pfam_acc = meta.get("accession", "")
            if not pfam_acc.startswith("PF"):
                continue
            name = meta.get("name", {})
            domain_name = name.get("name", "") if isinstance(name, dict) else str(name)

            mapping = entry.get("protein_structure_mapping", {})
            protein_mapping = mapping.get(protein_acc, [])
            if not protein_mapping:
                # Try iterating all keys
                for val in mapping.values():
                    if isinstance(val, list):
                        protein_mapping = val
                        break

            for fragment in protein_mapping:
                start = fragment.get("start")
                end = fragment.get("end")
                score = fragment.get("score")  # e-value

                if start is None or end is None:
                    continue

                domains.append({
                    "uniprot_acc": protein_acc,
                    "pfam_acc":    pfam_acc,
                    "domain_name": domain_name,
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

def fetch_interpro_domains_for_taxon(
    taxon_id: int,
    page_size: int = 200,
) -> list[dict[str, Any]]:
    """
    Fetch Pfam domain matches for all proteins in a given species from InterPro.

    Endpoint:
        /api/entry/pfam/protein/uniprot/taxonomy/uniprot/{taxon_id}
        ?page_size={page_size}&extra_fields=sequence_length

    Returns a list of domain dicts (one per domain-per-protein fragment).
    """
    url = f"{_BASE_URL}/entry/pfam/protein/uniprot/taxonomy/uniprot/{taxon_id}"
    params: dict[str, Any] = {
        "page_size": page_size,
        "extra_fields": "sequence_length",
    }

    all_domains: list[dict[str, Any]] = []
    page_num = 0

    while url:
        page_num += 1
        resp = _get_with_rate_limit(url, params if page_num == 1 else None)

        if resp.status_code != 200:
            logger.error(
                "InterPro HTTP %d for taxon %d page %d",
                resp.status_code, taxon_id, page_num,
            )
            break

        data = resp.json()
        results = data.get("results", [])

        for result in results:
            domains = _parse_domain_from_result(result)
            all_domains.extend(domains)

        next_url = data.get("next")
        url = next_url
        params = {}  # params only needed on first request

    logger.info(
        "InterPro fetch for taxon %d: %d domains from %d pages",
        taxon_id, len(all_domains), page_num,
    )
    return all_domains


# ─────────────────────────────────────────────────────────────────────────────
# enrich_existing_domains
# ─────────────────────────────────────────────────────────────────────────────

def enrich_existing_domains(taxon_id: int, driver) -> dict[str, int]:
    """
    Enrich Domain nodes (loaded by UniProt route) with e-values from InterPro.
    Only updates Domain nodes where e_value IS NULL — does not create new nodes.

    Returns:
        dict with keys: enriched, not_found
    """
    logger.info("Starting InterPro domain enrichment for taxon %d", taxon_id)

    domains = fetch_interpro_domains_for_taxon(taxon_id)

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
                result = session.run(query, batch=batch_rows, taxon_id=taxon_id)
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
