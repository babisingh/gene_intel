"""
Domain description lookup — three-layer pipeline (no SQLite required):

  Layer 1 — Static file (instant, offline-capable)
      domain_desc_lookup.json.gz ships with the repo.
      Covers ~27K Pfam + ~51K InterPro + ~48K GO entries.

  Layer 2 — Neo4j (already populated by prior queries or FTP ingest)
      Handled in evolution_queries.py: COALESCE(d.description, d.name, ...)
      Anything written back here is available on the next query with zero cost.

  Layer 3 — Public REST APIs (only for novel / rare IDs not in layers 1–2)
      EBI InterPro API  → Pfam, InterPro, PANTHER
      EBI QuickGO API   → GO terms
      Results written back to Neo4j Domain nodes so they are only fetched once.

Refresh the static file annually (or after Pfam/GO major releases):
    python backend/scripts/build_desc_lookup.py
"""

from __future__ import annotations

import gzip
import json
import logging
import time
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ── Static lookup file ────────────────────────────────────────────────────────

_LOOKUP_PATH = Path(__file__).parent / "domain_desc_lookup.json.gz"

# Loaded once at module import time
_STATIC: dict[str, dict[str, str]] = {"pfam": {}, "interpro": {}, "go": {}}


def _load_static() -> None:
    global _STATIC
    if not _LOOKUP_PATH.exists():
        logger.warning(
            "domain_desc_lookup.json.gz not found at %s — "
            "run backend/scripts/build_desc_lookup.py to generate it.",
            _LOOKUP_PATH,
        )
        return
    try:
        with gzip.open(_LOOKUP_PATH, "rb") as f:
            _STATIC = json.loads(f.read().decode())
        n = sum(len(v) for v in _STATIC.values())
        logger.info("Loaded %d domain descriptions from static lookup file.", n)
    except Exception as exc:
        logger.error("Failed to load domain_desc_lookup.json.gz: %s", exc)


_load_static()


def static_lookup(accession: str, source: str) -> str:
    """
    Look up a clean accession in the static dict.
    Returns the description string, or "" if not found.
    """
    src = source.lower()
    if src == "pfam" or accession.upper().startswith("PF"):
        return _STATIC.get("pfam", {}).get(accession, "")
    if src == "interpro" or accession.upper().startswith("IPR"):
        return _STATIC.get("interpro", {}).get(accession, "")
    if src == "go" or accession.upper().startswith("GO:"):
        return _STATIC.get("go", {}).get(accession, "")
    return ""


# ── API fallback ──────────────────────────────────────────────────────────────

_INTERPRO_BASE = "https://www.ebi.ac.uk/interpro/api/entry"
_QUICKGO_BASE  = "https://www.ebi.ac.uk/QuickGO/services/ontology/go/terms"
_TIMEOUT = 10
_RATE_DELAY = 0.3


def _fetch_interpro(acc: str) -> Optional[str]:
    """Fetch description from EBI InterPro REST API. Returns "" on known miss, None on error."""
    upper = acc.upper()
    if upper.startswith("PF"):
        url = f"{_INTERPRO_BASE}/pfam/{acc}"
    elif upper.startswith("IPR"):
        url = f"{_INTERPRO_BASE}/interpro/{acc}"
    elif upper.startswith("PTHR"):
        url = f"{_INTERPRO_BASE}/panther/{acc}"
    else:
        return ""
    try:
        resp = requests.get(url, headers={"Accept": "application/json"}, timeout=_TIMEOUT)
        if resp.status_code == 404:
            return ""
        resp.raise_for_status()
        name_obj = resp.json().get("metadata", {}).get("name", {})
        if isinstance(name_obj, dict):
            return name_obj.get("name") or name_obj.get("short") or ""
        return str(name_obj) if name_obj else ""
    except requests.RequestException as exc:
        logger.warning("InterPro API error for %s: %s", acc, exc)
        return None


def _fetch_quickgo(term_id: str) -> Optional[str]:
    """Fetch GO term name from QuickGO. Returns "" on known miss, None on transient error."""
    if not term_id.upper().startswith("GO:"):
        return ""
    try:
        resp = requests.get(f"{_QUICKGO_BASE}/{term_id}",
                            headers={"Accept": "application/json"}, timeout=_TIMEOUT)
        if resp.status_code == 404:
            return ""
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return results[0].get("name", "") if results else ""
    except requests.RequestException as exc:
        logger.warning("QuickGO API error for %s: %s", term_id, exc)
        return None


# ── Public interface ──────────────────────────────────────────────────────────

def enrich_descriptions(
    domain_display_ids: dict[str, str],   # {raw_domain_id: display_id}
    source_map: dict[str, str] | None = None,  # {raw_domain_id: source}
) -> dict[str, str]:
    """
    Return {raw_domain_id: description} for each entry.

    Uses the static file (layer 1) first — instant, no I/O.
    Falls back to public APIs (layer 3) only for IDs not covered.
    Neo4j write-back (layer 2) is handled by the caller.

    Returns "" for domains where no description is found anywhere.
    API fetch failures (transient) return "" rather than raising.
    """
    if not domain_display_ids:
        return {}

    result: dict[str, str] = {}
    source_map = source_map or {}

    # De-duplicate: multiple raw IDs may share the same display_id (e.g. BioMart ENSG__PF__N)
    display_to_raws: dict[str, list[str]] = {}
    for raw_id, display_id in domain_display_ids.items():
        if not display_id or display_id in ("—", ""):
            result[raw_id] = ""
            continue
        display_to_raws.setdefault(display_id, []).append(raw_id)

    # Layer 1 — static file
    needs_api: list[str] = []
    for display_id, raw_ids in display_to_raws.items():
        src = source_map.get(raw_ids[0], "")
        desc = static_lookup(display_id, src)
        if desc:
            for raw_id in raw_ids:
                result[raw_id] = desc
        else:
            needs_api.append(display_id)

    if not needs_api:
        return result

    logger.info(
        "Static lookup covered %d/%d display_ids; fetching %d from API",
        len(display_to_raws) - len(needs_api),
        len(display_to_raws),
        len(needs_api),
    )

    # Layer 3 — public APIs
    api_results: dict[str, str] = {}   # display_id → description
    for display_id in needs_api:
        time.sleep(_RATE_DELAY)
        upper = display_id.upper()
        if upper.startswith("GO:"):
            name = _fetch_quickgo(display_id)
        elif any(upper.startswith(p) for p in ("PF", "IPR", "PTHR")):
            name = _fetch_interpro(display_id)
        else:
            name = ""

        desc = name if name is not None else ""
        api_results[display_id] = desc

        raw_ids = display_to_raws.get(display_id, [])
        for raw_id in raw_ids:
            result[raw_id] = desc

    return result


def api_results_for_neo4j(
    api_descriptions: dict[str, str],   # display_id → description (from enrich_descriptions internals)
    domain_display_ids: dict[str, str], # raw_domain_id → display_id
) -> list[dict]:
    """
    Build a list of {domain_id, description} dicts ready for Neo4j write-back.
    Only includes entries where description is non-empty.
    """
    display_to_raws: dict[str, list[str]] = {}
    for raw_id, display_id in domain_display_ids.items():
        display_to_raws.setdefault(display_id, []).append(raw_id)

    updates = []
    for display_id, desc in api_descriptions.items():
        if desc:
            for raw_id in display_to_raws.get(display_id, []):
                updates.append({"domain_id": raw_id, "description": desc})
    return updates
