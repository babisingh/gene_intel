"""
Agent C: Visualizer & Explainer

Responsibility: Take raw Cypher results (a list of matched Gene nodes + their domains
and neighbourhood context) and produce a human-readable explanation tailored to the
user's selected persona.

Persona register:
  - investor:   Plain English, market framing, drug-target relevance highlighted
  - student:    Educational tone, biological concepts defined inline
  - researcher: Full metadata, technical terminology, Cypher query shown, export hint

Connected to:
  - graph_workflow.py: called after Agent A fetches results from Neo4j
  - api/search.py: persona string comes from the request body
  - frontend ExplainerCard.tsx: renders the returned explanation text
"""

from anthropic import Anthropic
from app.config import settings

client = Anthropic(api_key=settings.anthropic_api_key)

PERSONA_INSTRUCTIONS = {
    "investor": """
        You are explaining genomic findings to a biotech investor.
        - Use plain English — no jargon without immediate definition
        - Highlight commercial relevance: drug targets, conserved pathways, disease associations
        - Format: 2–3 short paragraphs. Lead with the most interesting finding.
        - End with: "Why this matters for drug discovery: ..."
    """,
    "student": """
        You are explaining genomic findings to a graduate biology student.
        - Use correct scientific terms but define them on first use in parentheses
        - Connect findings to concepts they would know: gene expression, protein domains, evolution
        - Format: structured explanation with "What we found:", "Why it's interesting:", "How it works:"
    """,
    "researcher": """
        You are explaining genomic findings to an expert bioinformatician.
        - Use full technical terminology — no simplification needed
        - Include: gene IDs, taxon IDs, domain accessions, exact property values
        - Note any caveats about data quality (transcript support level, annotation completeness)
        - Format: structured report with headings. Include the original Cypher query used.
    """,
}


def explain_results(
    nl_query: str,
    cypher_query: str,
    results: list,
    persona: str = "student",
) -> str:
    """
    Parameters:
      nl_query:    Original user question in natural language
      cypher_query: The Cypher Agent A generated (shown to researcher persona)
      results:     List of Neo4j result dicts from the search
      persona:     "investor" | "student" | "researcher"

    Returns: Plain-text explanation string
    """
    persona_instruction = PERSONA_INSTRUCTIONS.get(persona, PERSONA_INSTRUCTIONS["student"])

    # Format results for the LLM context (truncate to avoid huge prompts)
    results_summary = format_results_for_llm(results[:20])  # max 20 genes in context

    system = f"""
    You are Agent C of the Gene-Intel Discovery Engine.
    {persona_instruction}
    """

    user_message = (
        f'The user asked: "{nl_query}"\n\n'
        f"The search returned {len(results)} matching genes.\n"
        f"Here are the top results:\n\n"
        f"{results_summary}\n\n"
    )

    if persona == "researcher":
        user_message += f"The Cypher query used was:\n{cypher_query}\n\n"

    user_message += "Produce your explanation now."

    response = client.messages.create(
        model=settings.agent_llm_model,
        max_tokens=settings.agent_llm_max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text


def explain_single_gene(gene_data: dict, persona: str = "student") -> str:
    """Generate an explanation for a single gene detail view."""
    gene_name = gene_data.get("name", "unknown")
    species_name = gene_data.get("species_name", "unknown species")
    domains = ", ".join(gene_data.get("domains", [])[:10]) or "none annotated"

    persona_instruction = PERSONA_INSTRUCTIONS.get(persona, PERSONA_INSTRUCTIONS["student"])

    system = f"""
    You are Agent C of the Gene-Intel Discovery Engine.
    {persona_instruction}
    Keep the explanation to 2–3 paragraphs.
    """

    user_message = (
        f"Explain this gene to the user:\n\n"
        f"Gene: {gene_name} ({gene_data.get('gene_id', '')})\n"
        f"Species: {species_name} (taxon {gene_data.get('species_taxon', '')})\n"
        f"Biotype: {gene_data.get('biotype', 'unknown')}\n"
        f"Location: chr{gene_data.get('chromosome', '?')}:"
        f"{gene_data.get('start', 0)}–{gene_data.get('end', 0)} "
        f"({gene_data.get('strand', '?')} strand)\n"
        f"CDS length: {gene_data.get('cds_length', 0)} bp\n"
        f"Exon count: {gene_data.get('exon_count', 0)}\n"
        f"UTR/CDS ratio: {gene_data.get('utr_cds_ratio', 'N/A')}\n"
        f"Domains: {domains}\n"
    )

    response = client.messages.create(
        model=settings.agent_llm_model,
        max_tokens=settings.agent_llm_max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text


def format_results_for_llm(results: list) -> str:
    """
    Converts raw Neo4j result dicts to a readable summary for Agent C's context.
    Each result has: gene_id, name, species_taxon, biotype, cds_length, domains
    """
    lines = []
    for r in results:
        domains = ", ".join(r.get("domains", [])[:5]) or "none"
        lines.append(
            f"- {r.get('name', 'unnamed')} ({r.get('gene_id')}) | "
            f"Species taxon {r.get('species')} | "
            f"CDS: {r.get('cds_length')} bp | "
            f"Domains: {domains}"
        )
    return "\n".join(lines)
