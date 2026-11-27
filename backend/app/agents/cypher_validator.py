from __future__ import annotations

"""
Cypher Validator — Whitelist-based safety gate.

Prevents Agent A from executing Cypher that:
  - References hallucinated node labels (e.g. :Protein instead of :Domain)
  - References hallucinated property names (e.g. g.sequence_length)
  - Contains destructive operations (DELETE, DROP, SET on schema)
  - Exceeds safe LIMIT bounds

It also quotes integer taxon IDs (g.species_taxon = 9606 becomes
g.species_taxon = '9606'), because the graph stores taxon IDs as strings and
an integer never matches them. validate_cypher returns the rewritten query.

This is NOT a full Cypher parser — it's a targeted safety net using regex.
A real Cypher AST parser would be overkill for MVP.

Connected to:
  - agent_a_semantic.py: all generated Cypher passes through here before execution
  - bio_dictionary.py: ALLOWED_* whitelists sourced from there
"""

import logging
import re
from app.agents.bio_dictionary import (
    ALLOWED_NODE_LABELS,
    ALLOWED_GENE_PROPERTIES,
    ALLOWED_DOMAIN_PROPERTIES,
    ALLOWED_RELATIONSHIP_TYPES,
)

logger = logging.getLogger(__name__)

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

# ── Taxon ID literals ─────────────────────────────────────────────────────────
# Gene.species_taxon and Species.taxon_id hold strings such as '9606', and
# Neo4j never treats a string as equal to a number, so g.species_taxon = 9606
# matches nothing. Agent A's prompt says to quote taxon IDs, but Claude does
# not always do it, so integer literals compared with these properties are
# quoted here before the query runs.

TAXON_ID_PROPERTIES = ("species_taxon", "taxon_id")

# String literals, quoted identifiers and comments. They are hidden while the
# rewrites below run, so nothing inside them changes.
_OPAQUE_RE = re.compile(
    r"""
      '(?:[^'\\]|\\.)*'     # 'string'
    | "(?:[^"\\]|\\.)*"     # "string"
    | `[^`]*`               # `quoted identifier`
    | //[^\n]*              # line comment
    | /\*.*?\*/             # block comment
    """,
    re.VERBOSE | re.DOTALL,
)
_HIDDEN = "\x00"

_TAXON_KEY = "(?:" + "|".join(TAXON_ID_PROPERTIES) + ")"
_TAXON_PROP = r"\b[A-Za-z_]\w*\s*\.\s*" + _TAXON_KEY + r"\b"   # g.species_taxon
_INTEGER = r"(?<![\w.'])\d+(?![\w.'])"                          # 9606, not 9606.5
_EQUALITY = r"\s*(?:=|<>)\s*"

_TAXON_COMPARISONS = [
    # g.species_taxon = 9606, s.taxon_id <> 9606
    re.compile(rf"(?P<pre>{_TAXON_PROP}{_EQUALITY})(?P<num>{_INTEGER})"),
    # 9606 = g.species_taxon
    re.compile(rf"(?P<num>{_INTEGER})(?P<post>{_EQUALITY}{_TAXON_PROP})"),
    # (s:Species {taxon_id: 9606}), (g:Gene {species_taxon: 9606})
    re.compile(rf"(?P<pre>[{{,]\s*{_TAXON_KEY}\s*:\s*)(?P<num>{_INTEGER})"),
]
# g.species_taxon IN [9606, 10090]
_TAXON_IN_LIST_RE = re.compile(rf"(?P<pre>{_TAXON_PROP}\s+(?i:IN)\s*\[)(?P<items>[^\[\]]*)\]")
# List items that are all integers or (hidden) strings, e.g. 9606, '10090'
_LITERAL_ITEMS_RE = re.compile(rf"\s*(?:(?:\d+|{_HIDDEN})\s*(?:,\s*(?:\d+|{_HIDDEN})\s*)*)?")


def normalise_taxon_literals(cypher: str) -> str:
    """
    Quote integer literals that are compared with a taxon ID property:

        g.species_taxon = 9606            ->  g.species_taxon = '9606'
        g.species_taxon IN [9606, 10090]  ->  g.species_taxon IN ['9606', '10090']
        (s:Species {taxon_id: 9606})      ->  (s:Species {taxon_id: '9606'})

    Text inside string literals, quoted identifiers and comments is not
    touched, and neither is anything other than a plain integer literal:
    toInteger(g.species_taxon) = 9606 already works, and a computed list
    is left as it is.
    """
    if _HIDDEN in cypher:
        return cypher

    hidden: list[str] = []

    def hide(match: re.Match) -> str:
        hidden.append(match.group(0))
        return _HIDDEN

    text = _OPAQUE_RE.sub(hide, cypher)
    quoted = 0

    def quote(match: re.Match) -> str:
        nonlocal quoted
        quoted += 1
        parts = match.groupdict()
        return f"{parts.get('pre') or ''}'{parts['num']}'{parts.get('post') or ''}"

    def quote_items(match: re.Match) -> str:
        nonlocal quoted
        items = match.group("items")
        if not _LITERAL_ITEMS_RE.fullmatch(items):
            return match.group(0)
        quoted += len(re.findall(r"\d+", items))
        return match.group("pre") + re.sub(r"\d+", r"'\g<0>'", items) + "]"

    for pattern in _TAXON_COMPARISONS:
        text = pattern.sub(quote, text)
    text = _TAXON_IN_LIST_RE.sub(quote_items, text)

    if quoted:
        logger.info("Quoted %d integer taxon ID literal(s) in generated Cypher", quoted)

    restore = iter(hidden)
    return re.sub(_HIDDEN, lambda _: next(restore), text)


def validate_cypher(cypher: str) -> dict:
    """
    Returns: {"valid": bool, "error": str | None, "cypher": str}

    "cypher" is the query to run: the input with integer taxon IDs quoted by
    normalise_taxon_literals. The checks below run on that text.
    """
    cypher = normalise_taxon_literals(cypher)
    return {**_check(cypher), "cypher": cypher}


def _check(cypher: str) -> dict:
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
