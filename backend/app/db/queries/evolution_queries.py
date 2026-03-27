"""
Neo4j queries for cross-species evolutionary analysis.
Used by the /api/evolution/{gene_name} endpoint.
"""

import re
from app.db.domain_descriptions import enrich_descriptions


def get_gene_family_profiles(session, gene_name: str) -> list[dict]:
    """
    Fetch all genes matching gene_name (case-insensitive) across all species,
    with domain annotations and structural metrics.
    Returns one dict per gene instance found.
    """
    result = session.run(
        """
        MATCH (s:Species)-[:HAS_GENE]->(g:Gene)
        WHERE toLower(g.name) = toLower($name)
        OPTIONAL MATCH (g)-[:HAS_DOMAIN]->(d:Domain)
        OPTIONAL MATCH (g)-[:HAS_TRANSCRIPT]->(t:Transcript)
        WITH g, s,
             collect(DISTINCT d.domain_id) AS domains,
             count(DISTINCT t) AS transcript_count
        RETURN
            g.gene_id         AS gene_id,
            g.name            AS gene_name,
            g.biotype         AS biotype,
            g.exon_count      AS exon_count,
            g.cds_length      AS cds_length,
            g.utr_cds_ratio   AS utr_cds_ratio,
            g.utr5_length     AS utr5_length,
            g.utr3_length     AS utr3_length,
            g.chromosome      AS chromosome,
            g.start           AS start,
            g.end             AS end,
            g.strand          AS strand,
            s.taxon_id        AS taxon_id,
            s.name            AS species_name,
            s.common_name     AS common_name,
            s.assembly        AS assembly,
            domains,
            transcript_count
        ORDER BY s.name
        """,
        name=gene_name,
    )
    return [dict(r) for r in result]


def get_domain_descriptions(session, domain_ids: list[str]) -> dict[str, dict]:
    """
    Return {domain_id: {description, source, display_id}} for a list of domain_ids.

    Pipeline:
      1. Parse each domain_id to extract source + clean display_id.
      2. Query Neo4j Domain nodes — use d.name / d.ipr_name as fallbacks
         because BioMart always stores description="" but FTP ingests store
         the human-readable name in d.name.
      3. For any domain still missing a description, call the InterPro / QuickGO
         REST APIs (with a persistent SQLite cache) to fetch the real name.
    """
    if not domain_ids:
        return {}

    # Step 1 — parse all IDs upfront so we have source + display_id immediately
    parsed_map: dict[str, dict] = {did: _parse_domain_id(did) for did in domain_ids}

    # Step 2 — query Neo4j using the BEST available description field
    result = session.run(
        """
        MATCH (d:Domain)
        WHERE d.domain_id IN $ids
        RETURN d.domain_id AS domain_id,
               COALESCE(d.description, d.name, d.ipr_name, '') AS description,
               COALESCE(d.source, d.source_db, '') AS source
        """,
        ids=domain_ids,
    )
    db_data = {
        r["domain_id"]: {
            "description": r["description"] or "",
            "source":      r["source"] or "",
        }
        for r in result
    }

    # Build initial enriched map
    enriched: dict[str, dict] = {}
    for did in domain_ids:
        parsed = parsed_map[did]
        db     = db_data.get(did, {})
        enriched[did] = {
            "description": db.get("description") or "",
            "source":      db.get("source") or parsed["source"],
            "display_id":  parsed["display_id"],
        }

    # Step 3 — for domains with no description, call external APIs (cached)
    needs_api = {
        did: enriched[did]["display_id"]
        for did in domain_ids
        if not enriched[did]["description"]
        and enriched[did]["display_id"]
        and enriched[did]["display_id"] != "—"
    }
    if needs_api:
        api_descriptions = enrich_descriptions(needs_api)
        for did, desc in api_descriptions.items():
            if desc:
                enriched[did]["description"] = desc

    return enriched


# ── Domain ID parsing ─────────────────────────────────────────────────────────

def _parse_domain_id(domain_id: str) -> dict:
    """
    Parse raw domain_id into clean display components.

    Handles:
      "Pfam:PF00082"                    → source=Pfam, display_id=PF00082
      "GO:0043065"                      → source=GO, display_id=GO:0043065
      "InterPro:IPR000001"              → source=InterPro, display_id=IPR000001
      "ENSG00000141510__PF07710__312"   → source=Pfam, display_id=PF07710
      "ENSG00000141510__IPR000001__312" → source=InterPro, display_id=IPR000001
    """
    # Standard "Source:Accession" format
    if ":" in domain_id and not domain_id.startswith("ENSG"):
        source, acc = domain_id.split(":", 1)
        source = source.strip()
        acc = acc.strip()
        # Keep full "GO:NNNNNNN" as display_id so APIs and the frontend get the right key
        if source.upper() == "GO":
            return {"source": "GO", "display_id": f"GO:{acc}", "description": ""}
        return {
            "source": source,
            "display_id": acc,
            "description": "",
        }

    # BioMart format: GENEID__ACCESSION__POSITION
    if "__" in domain_id:
        parts = domain_id.split("__")
        if len(parts) >= 2:
            acc = parts[1].strip()
            if re.match(r"^PF\d+$", acc):
                return {"source": "Pfam", "display_id": acc, "description": ""}
            if re.match(r"^IPR\d+$", acc):
                return {"source": "InterPro", "display_id": acc, "description": ""}
            if re.match(r"^PTHR\d+", acc):
                return {"source": "PANTHER", "display_id": acc, "description": ""}
            if re.match(r"^G[Oo]:?\d+$", acc):
                clean = acc if acc.upper().startswith("GO:") else f"GO:{acc}"
                return {"source": "GO", "display_id": clean, "description": ""}
            return {"source": "Unknown", "display_id": acc, "description": ""}

    # Bare GO number (7-digit)
    if re.match(r"^\d{7}$", domain_id):
        return {"source": "GO", "display_id": f"GO:{domain_id}", "description": ""}

    # Bare PANTHER accession (PTHRXXXXX)
    if re.match(r"^PTHR\d+", domain_id, re.IGNORECASE):
        return {"source": "PANTHER", "display_id": domain_id.upper(), "description": ""}

    return {"source": "Unknown", "display_id": domain_id, "description": ""}

