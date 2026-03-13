"""
Agent A: Semantic Architect

Responsibility: Convert natural language queries into valid, efficient Cypher.

Approach (hybrid mode):
  1. Receive user NL query
  2. Build system prompt embedding the full Bio-Dictionary
  3. Call Claude API — Claude generates Cypher using Bio-Dictionary fragments
  4. Pass generated Cypher to cypher_validator.py for whitelist check
  5. If validation passes → execute against Neo4j
  6. If validation fails → ask Claude to revise with error context (max 2 retries)

Connected to:
  - bio_dictionary.py: source of system prompt content and validation whitelist
  - cypher_validator.py: validates Cypher before execution
  - graph_workflow.py: called as a LangGraph node in the search pipeline
  - neo4j_client.py: executes validated Cypher
"""

from anthropic import Anthropic
from app.agents.bio_dictionary import BIO_DICTIONARY, ALLOWED_GENE_PROPERTIES
from app.agents.cypher_validator import validate_cypher
from app.config import settings

client = Anthropic(api_key=settings.anthropic_api_key)

SYSTEM_PROMPT = """
You are Agent A of the Gene-Intel Discovery Engine. Your sole job is to convert
natural language genomic queries into valid Neo4j Cypher.

## The Graph Schema
Nodes: :Species, :Gene, :Transcript, :Feature, :Domain
Relationships:
  (:Species)-[:HAS_GENE]->(:Gene)
  (:Gene)-[:HAS_TRANSCRIPT]->(:Transcript)
  (:Transcript)-[:HAS_FEATURE]->(:Feature)
  (:Gene)-[:HAS_DOMAIN]->(:Domain)
  (:Gene)-[:CO_LOCATED_WITH {{distance_bp: Int}}]->(:Gene)

## Valid Gene Properties
{gene_props}

## The Bio-Dictionary (use these fragments as building blocks)
{bio_dict}

## Rules
1. Always RETURN g as gene, collect(DISTINCT d.domain_id) as domains, g.species_taxon as species
2. Always LIMIT results to 300 unless the user specifies otherwise
3. Use only property names from the Valid Gene Properties list above
4. For cross-species queries, filter with WHERE g.species_taxon IN [list_of_taxon_ids]
5. Prefer MATCH + WHERE over complex sub-queries for readability
6. Output ONLY the Cypher query — no explanation, no markdown, no backticks
"""


def build_system_prompt() -> str:
    bio_dict_text = "\n".join(
        f"- '{concept}': WHERE {entry.get('cypher_where', '')} "
        f"({entry['description']})"
        for concept, entry in BIO_DICTIONARY.items()
    )
    return SYSTEM_PROMPT.format(
        gene_props=", ".join(sorted(ALLOWED_GENE_PROPERTIES)),
        bio_dict=bio_dict_text,
    )


def generate_cypher(nl_query: str, retry_context: str = "") -> dict:
    """
    Returns: {"cypher": str, "success": bool, "error": str | None}
    """
    user_message = nl_query
    if retry_context:
        user_message += (
            f"\n\nPrevious attempt failed validation: {retry_context}"
            "\nPlease fix and retry."
        )

    response = client.messages.create(
        model=settings.agent_llm_model,
        max_tokens=settings.agent_llm_max_tokens,
        system=build_system_prompt(),
        messages=[{"role": "user", "content": user_message}],
    )

    cypher = response.content[0].text.strip()

    # Validate before returning
    validation = validate_cypher(cypher)
    if not validation["valid"]:
        return {"cypher": cypher, "success": False, "error": validation["error"]}

    return {"cypher": cypher, "success": True, "error": None}


def generate_cypher_with_retry(nl_query: str, max_retries: int = 2) -> dict:
    """Wraps generate_cypher with up to max_retries revision attempts."""
    result = generate_cypher(nl_query)
    for _ in range(max_retries):
        if result["success"]:
            return result
        result = generate_cypher(nl_query, retry_context=result["error"])
    return result  # Return last attempt even if failed — caller handles error
