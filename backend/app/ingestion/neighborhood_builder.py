"""
Sliding-window neighborhood builder.

For every gene G on a chromosome, finds all genes N where:
    |G.start - N.end| < NEIGHBORHOOD_WINDOW_BP   (default 10,000 bp)

Creates a CO_LOCATED_WITH relationship between each pair.
This is computed per-chromosome to keep the window scan O(n) not O(n²).

ELI15 analogy: Imagine sorting all genes on a chromosome by their start position
like books on a shelf by page number. We then slide a ruler across the shelf —
any two books whose covers overlap within 10,000 pages are "neighbours".

Connected to:
  - batch_writer.py: CO_LOCATED_WITH edge dicts are passed to write_edges_batch()
  - Neo4j schema: CO_LOCATED_WITH relationship with distance_bp property
"""

from collections import defaultdict
from typing import List, Dict
import os

WINDOW_BP = int(os.getenv("NEIGHBORHOOD_WINDOW_BP", 10000))


def build_neighborhood_edges(genes: List[Dict], window_bp: int = WINDOW_BP) -> List[Dict]:
    """
    Input:  list of gene dicts with gene_id, chromosome, start, end
    Output: list of edge dicts {from_id, to_id, distance_bp}

    Deduplicates pairs — only one edge per (A, B) pair regardless of direction.
    """
    # Group genes by chromosome for efficient windowing
    by_chrom: Dict[str, List[Dict]] = defaultdict(list)
    for g in genes:
        by_chrom[g["chromosome"]].append(g)

    edges = []
    seen_pairs: set = set()

    for chrom, chrom_genes in by_chrom.items():
        # Sort by start position — enables the sliding window
        sorted_genes = sorted(chrom_genes, key=lambda g: g["start"])

        for i, gene_a in enumerate(sorted_genes):
            # Walk forward until we exceed the window
            j = i + 1
            while j < len(sorted_genes):
                gene_b = sorted_genes[j]
                distance = gene_b["start"] - gene_a["end"]
                if distance > window_bp:
                    break  # All further genes are farther away — exit inner loop

                pair_key = tuple(sorted([gene_a["gene_id"], gene_b["gene_id"]]))
                if pair_key not in seen_pairs:
                    seen_pairs.add(pair_key)
                    edges.append({
                        "from_id":     gene_a["gene_id"],
                        "to_id":       gene_b["gene_id"],
                        "distance_bp": abs(distance),
                    })
                j += 1

    return edges
