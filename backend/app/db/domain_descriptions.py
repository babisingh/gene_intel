"""
Domain description lookup with persistent SQLite cache.

Fetches human-readable names for domain accessions from public REST APIs:
  - Pfam / InterPro / PANTHER → EBI InterPro API
  - GO terms                  → EBI QuickGO API

Results are stored in a local SQLite file (data/desc_cache.db) so each
accession is only fetched once, even across server restarts.

Public API docs:
  InterPro: https://www.ebi.ac.uk/interpro/api/
  QuickGO:  https://www.ebi.ac.uk/QuickGO/services/ontology/go/terms/{id}
"""

from __future__ import annotations

import logging
import re
import sqlite3
import time
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

_CACHE_PATH = Path(__file__).parent.parent.parent / "data" / "desc_cache.db"
_INTERPRO_BASE = "https://www.ebi.ac.uk/interpro/api/entry"
_QUICKGO_BASE  = "https://www.ebi.ac.uk/QuickGO/services/ontology/go/terms"
_REQUEST_TIMEOUT = 10
_RATE_DELAY = 0.3   # seconds between API calls to be a polite client

# ── SQLite helpers ─────────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    """Return a connection to the cache DB, creating it if needed."""
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_CACHE_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS domain_desc (
            accession   TEXT PRIMARY KEY,
            name        TEXT NOT NULL DEFAULT '',
            fetched_ok  INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    return conn


def _cache_get(conn: sqlite3.Connection, accessions: list[str]) -> dict[str, str]:
    """Return {accession: name} for accessions already in the cache."""
    if not accessions:
        return {}
    placeholders = ",".join("?" * len(accessions))
    rows = conn.execute(
        f"SELECT accession, name FROM domain_desc WHERE accession IN ({placeholders})",
        accessions,
    ).fetchall()
    return {row[0]: row[1] for row in rows}


def _cache_set(conn: sqlite3.Connection, acc: str, name: str, ok: bool) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO domain_desc (accession, name, fetched_ok) VALUES (?, ?, ?)",
        (acc, name, 1 if ok else 0),
    )
    conn.commit()


def _was_attempted(conn: sqlite3.Connection, accessions: list[str]) -> set[str]:
    """Return accessions already attempted (whether or not they returned a name)."""
    if not accessions:
        return set()
    placeholders = ",".join("?" * len(accessions))
    rows = conn.execute(
        f"SELECT accession FROM domain_desc WHERE accession IN ({placeholders})",
        accessions,
    ).fetchall()
    return {row[0] for row in rows}


# ── API fetchers ──────────────────────────────────────────────────────────────

def _fetch_interpro(acc: str) -> Optional[str]:
    """
    Fetch description for a Pfam / InterPro / PANTHER accession.
    Returns the human-readable name string, or None on failure.
    """
    # Determine the InterPro sub-endpoint based on prefix
    if acc.upper().startswith("PF"):
        endpoint = f"{_INTERPRO_BASE}/pfam/{acc}"
    elif acc.upper().startswith("IPR"):
        endpoint = f"{_INTERPRO_BASE}/interpro/{acc}"
    elif acc.upper().startswith("PTHR"):
        endpoint = f"{_INTERPRO_BASE}/panther/{acc}"
    else:
        return None

    try:
        resp = requests.get(
            endpoint,
            headers={"Accept": "application/json"},
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code == 404:
            return ""   # Valid miss — accession does not exist
        resp.raise_for_status()
        data = resp.json()
        # InterPro API nests the name: metadata.name.name
        name_obj = data.get("metadata", {}).get("name", {})
        if isinstance(name_obj, dict):
            return name_obj.get("name") or name_obj.get("short") or ""
        if isinstance(name_obj, str):
            return name_obj
        return ""
    except requests.RequestException as exc:
        logger.warning("InterPro API error for %s: %s", acc, exc)
        return None   # Transient failure — don't cache


def _fetch_quickgo(term_id: str) -> Optional[str]:
    """
    Fetch the name for a GO term via QuickGO REST API.
    term_id must include the 'GO:' prefix (e.g. 'GO:0043065').
    Returns the term name string, or None on transient failure.
    """
    if not term_id.upper().startswith("GO:"):
        return ""

    try:
        resp = requests.get(
            f"{_QUICKGO_BASE}/{term_id}",
            headers={"Accept": "application/json"},
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code == 404:
            return ""
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if results:
            return results[0].get("name", "")
        return ""
    except requests.RequestException as exc:
        logger.warning("QuickGO API error for %s: %s", term_id, exc)
        return None


# ── Public interface ──────────────────────────────────────────────────────────

def enrich_descriptions(
    domain_display_ids: dict[str, str],   # {raw_domain_id: display_id}
) -> dict[str, str]:
    """
    Given a mapping of raw_domain_id → clean_accession (display_id), return
    {raw_domain_id: description_string} for each entry.

    Hits the SQLite cache first; only calls external APIs for unknown accessions.
    Rate-limited to be polite to public APIs.

    Args:
        domain_display_ids: dict mapping raw_domain_id to its clean display_id
            e.g. {"GO:0043065": "GO:0043065", "Pfam:PF07710": "PF07710",
                  "ENSG00000141510__PF07710__312": "PF07710"}

    Returns:
        {raw_domain_id: description}  where description may be "" if not found.
    """
    if not domain_display_ids:
        return {}

    conn = _get_conn()
    result: dict[str, str] = {}

    # De-duplicate: multiple raw IDs may map to the same display_id
    # e.g. many BioMart-format IDs might share PF07710
    display_to_raws: dict[str, list[str]] = {}
    for raw_id, display_id in domain_display_ids.items():
        if not display_id or display_id == "—":
            result[raw_id] = ""
            continue
        display_to_raws.setdefault(display_id, []).append(raw_id)

    unique_accessions = list(display_to_raws.keys())

    # 1. Check what's already cached
    cached = _cache_get(conn, unique_accessions)
    attempted = _was_attempted(conn, unique_accessions)

    # Fill from cache
    for acc, name in cached.items():
        for raw_id in display_to_raws.get(acc, []):
            result[raw_id] = name

    # 2. Fetch uncached accessions
    to_fetch = [acc for acc in unique_accessions if acc not in attempted]
    logger.info("Domain description lookup: %d cached, %d to fetch from API",
                len(cached), len(to_fetch))

    for acc in to_fetch:
        time.sleep(_RATE_DELAY)

        # Determine which API to use based on accession prefix
        name: Optional[str]
        upper = acc.upper()
        if upper.startswith("GO:"):
            name = _fetch_quickgo(acc)
        elif upper.startswith("PF") or upper.startswith("IPR") or upper.startswith("PTHR"):
            name = _fetch_interpro(acc)
        else:
            # Unknown accession type — mark as attempted with empty name
            name = ""

        if name is None:
            # Transient failure — skip caching so we retry next time
            logger.debug("Skipping cache for %s (transient API failure)", acc)
            for raw_id in display_to_raws.get(acc, []):
                result[raw_id] = ""
            continue

        _cache_set(conn, acc, name, ok=True)
        for raw_id in display_to_raws.get(acc, []):
            result[raw_id] = name

    conn.close()
    return result
