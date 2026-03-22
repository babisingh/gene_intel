from __future__ import annotations

"""
Cypher Validator — Whitelist-based safety gate.

Prevents Agent A from executing Cypher that:
  - References hallucinated node labels (e.g. :Protein instead of :Domain)
  - References hallucinated property names (e.g. g.sequence_length)
  - Contains destructive operations (DELETE, DROP, SET on schema)
  - Exceeds safe LIMIT bounds

This is NOT a full Cypher parser — it's a targeted safety net using regex.
A real Cypher AST parser would be overkill for MVP.

Connected to:
  - agent_a_semantic.py: all generated Cypher passes through here before execution
  - bio_dictionary.py: ALLOWED_* whitelists sourced from there
"""

import re
from app.agents.bio_dictionary import (
    ALLOWED_NODE_LABELS,
    ALLOWED_GENE_PROPERTIES,
    ALLOWED_DOMAIN_PROPERTIES,
    ALLOWED_RELATIONSHIP_TYPES,
)

FORBIDDEN_PATTERNS = [
    (r"\bDELETE\b", "Destructive DELETE operation not allowed"),
    (r"\bDROP\b",   "Destructive DROP operation not allowed"),
    (r"\bREMOVE\b", "Destructive REMOVE operation not allowed"),
    (r"\bSET\s+[a-z]", "SET operations not allowed in search queries"),
    (r"\bCREATE\b", "CREATE operations not allowed in search queries"),
    (r"\bMERGE\b",  "MERGE operations not allowed in search queries"),
]

ALL_ALLOWED_PROPS = (
    ALLOWED_GENE_PROPERTIES
    | ALLOWED_DOMAIN_PROPERTIES
    | {"transcript_id", "type", "exon_count", "support_level"}
    | {"distance_bp", "taxon_id", "name", "common_name", "kingdom"}
)


def validate_cypher(cypher: str) -> dict:
    """
    Returns: {"valid": bool, "error": str | None}
    """
    cypher_upper = cypher.upper()

    # 1. Block destructive operations
    for pattern, message in FORBIDDEN_PATTERNS:
        if re.search(pattern, cypher, re.IGNORECASE):
            return {"valid": False, "error": message}

    # 2. Check for RETURN clause (all queries must return something)
    if "RETURN" not in cypher_upper:
        return {"valid": False, "error": "Query must contain a RETURN clause"}

    # 3. Check LIMIT exists
    if "LIMIT" not in cypher_upper:
        return {"valid": False, "error": "Query must contain a LIMIT clause (max 300)"}

    # 4. Check node labels used in the query are in the whitelist
    # Strip string literals first to avoid false positives (e.g. 'Pfam:PF00069')
    cypher_no_strings = re.sub(r"'[^']*'", "''", cypher)
    cypher_no_strings = re.sub(r'"[^"]*"', '""', cypher_no_strings)
    # Extract node labels: patterns like (:Label) or (alias:Label) — inside round brackets
    # Exclude relationship types which appear inside square brackets [...]
    cypher_no_rel_types = re.sub(r'\[[^\]]*\]', '[]', cypher_no_strings)
    used_labels = set(re.findall(r':([A-Z][A-Za-z]+)', cypher_no_rel_types))
    all_allowed = ALLOWED_NODE_LABELS | ALLOWED_RELATIONSHIP_TYPES
    unknown_labels = used_labels - all_allowed
    if unknown_labels:
        return {"valid": False, "error": f"Unknown node label(s): {unknown_labels}"}

    # 5. Check property names (g.something, d.something, etc.)
    used_props = set(re.findall(r'\b[a-z]\.[a-z_]+\b', cypher))
    prop_names = {p.split(".")[1] for p in used_props if "." in p}
    unknown_props = prop_names - ALL_ALLOWED_PROPS
    if unknown_props:
        return {
            "valid": False,
            "error": (
                f"Unknown property name(s): {unknown_props}. "
                f"Allowed: {sorted(ALL_ALLOWED_PROPS)}"
            ),
        }

    return {"valid": True, "error": None}
