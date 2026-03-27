"""
Agent Evo: generates an evolutionary narrative for a gene family.

Takes the cross-species structural profile (domains, exon counts, UTR ratios,
transcript counts) plus Dollo parsimony domain events and produces a
scientifically grounded 3-4 paragraph narrative using Claude.
"""

import logging
from anthropic import Anthropic
from app.config import settings
from app.evolution.phylo_tree import SPECIES_META

logger = logging.getLogger(__name__)
client = Anthropic(api_key=settings.anthropic_api_key)


def generate_evolutionary_narrative(
    gene_name: str,
    species_profiles: list[dict],
    domain_events: list[dict],
    domain_ages: list[dict],
) -> str:
    """
    Parameters
    ----------
    gene_name      : searched gene symbol
    species_profiles: list of per-species dicts (from evolution_queries)
    domain_events  : gain/loss events from Dollo parsimony
    domain_ages    : domain age classification dicts

    Returns: markdown-formatted narrative string
    """
    all_taxon_ids = {p["taxon_id"] for p in species_profiles}
    absent_species = [
        SPECIES_META[t]["common"]
        for t in SPECIES_META
        if t not in all_taxon_ids
    ]

    # Build compact per-species summary for LLM context
    species_lines = []
    for p in species_profiles:
        doms = (p.get("domains") or [])[:6]
        dom_str = ", ".join(doms) if doms else "none annotated"
        species_lines.append(
            f"  {p.get('common_name', p.get('species_name', '?'))} "
            f"({p.get('species_name', '?')}): "
            f"exons={p.get('exon_count', 'N/A')}, "
            f"CDS={p.get('cds_length', 'N/A')} bp, "
            f"UTR/CDS={round(p.get('utr_cds_ratio') or 0, 2)}, "
            f"isoforms={p.get('transcript_count', 0)}, "
            f"domains=[{dom_str}]"
        )

    # Domain gain/loss summary
    event_lines = []
    for ev in domain_events:
        if ev["type"] == "gain":
            event_lines.append(
                f"  GAINED {ev['domain_id']} at {ev['node_label']} (~{ev['time_mya']} Mya)"
            )
        else:
            sp = ", ".join((ev.get("species") or [])[:3])
            event_lines.append(
                f"  LOST {ev['domain_id']} in {ev['node_label']} ({sp})"
            )

    # Domain age summary
    age_lines = [
        f"  {a['domain_id']}: {a['age']['label']}"
        for a in domain_ages[:15]  # cap for prompt length
    ]

    user_message = f"""
Gene family: **{gene_name}**
Present in {len(species_profiles)} species: {', '.join(p.get('common_name', '') for p in species_profiles)}
Absent in: {', '.join(absent_species[:8])}

Per-species structural profiles (phylogenetically ordered):
{chr(10).join(species_lines)}

Domain evolutionary events (Dollo parsimony reconstruction):
{chr(10).join(event_lines) if event_lines else '  No domain events computed (no domain annotations found)'}

Domain age classifications:
{chr(10).join(age_lines) if age_lines else '  No domain age data'}

Write a scientific evolutionary narrative for {gene_name} with these four markdown sections:

## Origin & Conservation
When and where did this gene originate? Which clades have it, which don't? What does the
taxonomic distribution imply about the gene's age and evolutionary origin?

## Domain Architecture Evolution
What domain gain/loss events occurred? What do they imply functionally? Are there lineage-specific
domain innovations or losses? Reference specific domain IDs and times in Mya.

## Structural Complexity Trajectory
How did exon count, UTR length, CDS length, and isoform number change across the tree?
Identify specific lineages with notable increases or decreases.

## Evolutionary Hypotheses
Based on the data above, propose 2-3 testable hypotheses about this gene's evolution.
Be specific about which lineages and time windows to investigate.

Use precise Mya values. Reference specific species by common name. Be scientifically rigorous.
"""

    try:
        response = client.messages.create(
            model=settings.agent_llm_model,
            max_tokens=2000,
            system="""You are an expert comparative genomicist writing for a Nature Methods paper.
Generate evolutionary narratives that are hypothesis-driven, data-grounded, and scientifically
precise. Use markdown headers as instructed. Only make claims supported by the data provided.
Reference specific domain IDs, clade names, and Mya estimates from the input.""",
            messages=[{"role": "user", "content": user_message}],
        )
    except Exception as e:
        logger.error("agent_evo LLM call failed: %s", e)
        return f"*Narrative generation failed: {e}*"

    if not response.content:
        return "*Narrative generation returned empty response.*"

    return response.content[0].text
