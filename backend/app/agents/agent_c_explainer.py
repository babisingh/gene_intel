"""
Agent C: Visualizer & Explainer

Responsibility: Take raw Cypher results (a list of matched Gene nodes + their domains
and neighbourhood context) and produce a human-readable explanation tailored to the
user's selected persona.

Persona register:
  - business:    Plain English, market framing, drug-target relevance highlighted
  - student:     Educational tone, biological concepts defined inline
  - researcher:  Full metadata, technical terminology, Cypher query shown, export hint

Connected to:
  - graph_workflow.py: called after Agent A fetches results from Neo4j
  - api/search.py: persona string comes from the request body
  - frontend ExplainerCard.tsx: renders the returned explanation text
"""

from typing import Optional

from anthropic import Anthropic
from app.agents.llm_reply import reply_text
from app.config import settings

client = Anthropic(api_key=settings.anthropic_api_key)

PERSONA_INSTRUCTIONS = {
    "business": """
        You are explaining genomic findings to a biotech business professional or investor.
        - Use plain English only — define any scientific term immediately when used
        - Highlight commercial and strategic relevance: drug targets, conserved pathways,
          disease associations, competitive moats, and unmet medical needs
        - Quantify where possible: number of genes found, how many species share the finding,
          known drug approvals in this pathway
        - Avoid raw identifiers (gene IDs, taxon IDs) — always use common names
        - Format: 2–3 short paragraphs. Open with the headline finding.
          Close with a "Business significance:" paragraph.
    """,
    "student": """
        You are explaining genomic findings to a graduate biology student.
        - Use correct scientific terminology, defining each new term in parentheses on first use
        - Connect findings to core concepts the student would know: gene expression, protein
          domains, evolutionary conservation, gene regulation, splicing
        - Use analogies where helpful to clarify complex ideas
        - Format four clearly labelled sections:
          "What we found:" | "Why it's interesting:" | "How it works:" | "What it means:"
    """,
    "researcher": """
        You are explaining genomic findings to an expert bioinformatician or molecular biologist.
        - Use full technical terminology — no simplification needed
        - Include exact gene IDs, taxon IDs, domain accessions (Pfam/InterPro/GO/KEGG),
          chromosomal coordinates, and strand orientation where available
        - Note data quality caveats: transcript support level, annotation completeness,
          BioMart domain coverage gaps
        - Format with markdown headings: ## Summary | ## Key Findings | ## Technical Details | ## Caveats
        - When the Cypher query is provided, briefly explain its logic after presenting results
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
      persona:     "business" | "student" | "researcher"

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

    return reply_text(response)


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
        f"{describe_gene_values(gene_data)}"
        f"Domains: {domains}\n"
    )

    response = client.messages.create(
        model=settings.agent_llm_model,
        max_tokens=settings.agent_llm_max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )

    return reply_text(response)


def format_results_for_llm(results: list) -> str:
    """
    Converts raw Neo4j result dicts to a readable summary for Agent C's context.
    Each result has the Gene properties (gene_id, name, cds_length,
    exon_count, canonical_source, ...) plus domains and species.
    """
    lines = []
    summed = False
    for r in results:
        domains = ", ".join(r.get("domains", [])[:5]) or "none"
        label = gene_values_label(r)
        summed = summed or label == SUMMED_LABEL
        cds = f"CDS: {r.get('cds_length')} bp ({label})" if label else "CDS: not available"
        lines.append(
            f"- {r.get('name', 'unnamed')} ({r.get('gene_id')}) | "
            f"Species taxon {r.get('species')} | "
            f"{cds} | "
            f"Domains: {domains}"
        )
    if summed:
        lines.append(
            f"\nCDS lengths marked '{SUMMED_LABEL}' are totals over a gene's "
            "isoforms, not the length of one coding sequence: do not convert "
            "them into protein lengths."
        )
    return "\n".join(lines)


# How feature_extractor.py chose the transcript a gene's values describe.
_SOURCE_TEXT = {
    "Ensembl_canonical": "its canonical transcript, as tagged in the annotation",
    "longest_cds": ("the transcript with the longest coding sequence, because the "
                    "annotation tags no canonical transcript for this gene"),
    "longest_transcript": ("its longest transcript, because the annotation tags no "
                           "canonical transcript and none has a coding sequence"),
}
_SOURCE_LABEL = {
    "Ensembl_canonical": "canonical transcript",
    "longest_cds": "transcript with the longest CDS",
    "longest_transcript": "longest transcript",
}
SUMMED_LABEL = "summed over all transcripts"


def gene_values_label(gene: dict) -> Optional[str]:
    """
    Which transcript a gene's cds_length, exon_count and utr_cds_ratio
    describe, as a short label; None for a gene without transcripts.

    A graph built before canonical_source existed sums every transcript
    instead, so its genes are labelled as sums.
    """
    source = gene.get("canonical_source")
    if source in _SOURCE_LABEL:
        return _SOURCE_LABEL[source]
    return SUMMED_LABEL if gene.get("exon_count") else None


def describe_gene_values(gene: dict) -> str:
    """
    The CDS length, exon count and UTR/CDS ratio lines of Agent C's prompt,
    saying which transcript they describe.

    Sums over all transcripts (graphs built before canonical_source existed)
    are labelled as sums, with a note not to convert them: Claude once turned
    TTN's 577,563 bp sum into a 192,521 amino acid protein.
    """
    cds = gene.get("cds_length") or 0
    exons = gene.get("exon_count") or 0
    ratio = gene.get("utr_cds_ratio")
    ratio_text = "N/A" if ratio is None else ratio
    source = gene.get("canonical_source")

    if source in _SOURCE_TEXT:
        protein = f" (about {cds // 3} amino acids)" if cds else " (no coding sequence)"
        return (
            f"CDS length: {cds} bp{protein}\n"
            f"Exon count: {exons}\n"
            f"UTR/CDS ratio: {ratio_text}\n"
            f"These three values describe transcript {gene.get('canonical_transcript_id')}, "
            f"{_SOURCE_TEXT[source]}.\n"
        )
    if exons:
        return (
            f"CDS length, summed over all of the gene's transcripts: {cds} bp\n"
            f"Exon count, summed over all of the gene's transcripts: {exons}\n"
            f"UTR/CDS ratio of those sums: {ratio_text}\n"
            "These are totals over the gene's isoforms, not the length of one "
            "coding sequence or the exons of one transcript. Do not convert the "
            "CDS total into a protein length.\n"
        )
    return "CDS length and exon count: not available (no transcripts for this gene in the graph)\n"
