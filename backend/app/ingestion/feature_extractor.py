"""
Feature extractor — builds Gene/Transcript/Feature node dicts from parsed GTF records.

Takes the stream of dicts from gtf_parser.py and accumulates them into structured
Gene, Transcript, and Feature collections for batch writing.

Connected to:
  - gtf_parser.py: consumes yielded records
  - biomart_parser.py: domain dicts are merged in after extraction
  - batch_writer.py: output dicts are written to Neo4j
"""

from typing import Dict, List, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


def extract_features(
    records,  # Generator from parse_gtf_streaming
    species_taxon: str,
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Consume all records from the GTF parser and return:
        (genes, transcripts, features)

    Each gene dict matches the :Gene schema.
    Each transcript dict matches the :Transcript schema.
    Each feature dict matches the :Feature schema.
    """
    genes: Dict[str, Dict] = {}
    transcripts: Dict[str, Dict] = {}
    features: List[Dict] = []

    # Accumulators for computed gene properties
    gene_cds_lengths: Dict[str, int] = defaultdict(int)
    gene_utr5_lengths: Dict[str, int] = defaultdict(int)
    gene_utr3_lengths: Dict[str, int] = defaultdict(int)
    gene_exon_counts: Dict[str, int] = defaultdict(int)

    # Track feature rank per transcript+type
    feature_ranks: Dict[str, int] = defaultdict(int)

    for rec in records:
        attrs = rec["attributes"]
        f_type = rec["feature_type"]

        if f_type == "gene":
            gene_id = attrs.get("gene_id", "").strip()
            if not gene_id:
                continue
            length = rec["end"] - rec["start"]
            genes[gene_id] = {
                "gene_id":      gene_id,
                "name":         attrs.get("gene_name", attrs.get("Name", gene_id)),
                "biotype":      attrs.get("gene_biotype", attrs.get("gene_type", "unknown")),
                "chromosome":   rec["chromosome"],
                "start":        rec["start"],
                "end":          rec["end"],
                "strand":       rec["strand"],
                "length":       length,
                "species_taxon": species_taxon,
                # These will be filled in below
                "cds_length":   0,
                "exon_count":   0,
                "utr5_length":  0,
                "utr3_length":  0,
                "utr_cds_ratio": None,
            }

        elif f_type == "transcript":
            transcript_id = attrs.get("transcript_id", "").strip()
            gene_id = attrs.get("gene_id", "").strip()
            if not transcript_id or not gene_id:
                continue
            support_raw = attrs.get("transcript_support_level", None)
            support_level = None
            if support_raw and support_raw.isdigit():
                support_level = int(support_raw)
            transcripts[transcript_id] = {
                "transcript_id": transcript_id,
                "gene_id":       gene_id,
                "type":          attrs.get("transcript_biotype", attrs.get("transcript_type", "mRNA")),
                "exon_count":    0,
                "support_level": support_level,
                "is_canonical":  False,
            }

        elif f_type in ("CDS", "exon", "UTR", "five_prime_utr", "three_prime_utr",
                        "start_codon", "stop_codon"):
            transcript_id = attrs.get("transcript_id", "").strip()
            gene_id = attrs.get("gene_id", "").strip()
            if not transcript_id:
                continue

            # Normalise UTR type
            normalised_type = f_type
            if f_type == "five_prime_utr":
                normalised_type = "UTR"
            elif f_type == "three_prime_utr":
                normalised_type = "UTR"

            rank_key = f"{transcript_id}_{normalised_type}"
            feature_ranks[rank_key] += 1
            rank = feature_ranks[rank_key]
            feature_id = f"{transcript_id}_{normalised_type}_{rank}"
            length = rec["end"] - rec["start"]

            features.append({
                "feature_id":    feature_id,
                "transcript_id": transcript_id,
                "type":          normalised_type,
                "length":        length,
                "rank":          rank,
                "start":         rec["start"],
                "end":           rec["end"],
            })

            # Accumulate gene-level properties
            if gene_id:
                if f_type == "CDS":
                    gene_cds_lengths[gene_id] += length
                elif f_type in ("UTR", "five_prime_utr"):
                    gene_utr5_lengths[gene_id] += length
                elif f_type == "three_prime_utr":
                    gene_utr3_lengths[gene_id] += length
                elif f_type == "exon":
                    gene_exon_counts[gene_id] += 1

            # Update transcript exon count
            if f_type == "exon" and transcript_id in transcripts:
                transcripts[transcript_id]["exon_count"] += 1

    # Back-fill computed properties onto gene dicts
    for gene_id, gene in genes.items():
        cds = gene_cds_lengths.get(gene_id, 0)
        utr5 = gene_utr5_lengths.get(gene_id, 0)
        utr3 = gene_utr3_lengths.get(gene_id, 0)
        exons = gene_exon_counts.get(gene_id, 0)

        gene["cds_length"] = cds
        gene["utr5_length"] = utr5
        gene["utr3_length"] = utr3
        gene["exon_count"] = exons
        if cds > 0:
            gene["utr_cds_ratio"] = round((utr5 + utr3) / cds, 4)

    logger.info(
        "Extracted %d genes, %d transcripts, %d features for taxon %s",
        len(genes), len(transcripts), len(features), species_taxon,
    )

    return list(genes.values()), list(transcripts.values()), features
