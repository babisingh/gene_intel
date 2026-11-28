"""
Feature extractor — builds Gene/Transcript/Feature node dicts from parsed GTF records.

Takes the stream of dicts from gtf_parser.py and accumulates them into structured
Gene, Transcript, and Feature collections for batch writing.

A gene's cds_length, exon_count, utr5_length, utr3_length and utr_cds_ratio
describe one transcript, the gene's canonical transcript, never a sum over
its isoforms (a sum counts every shared exon once per isoform: TTN came out
with 577,563 bp of CDS and 1,700 exons). The canonical transcript is the one
the annotation tags "Ensembl_canonical". For a gene without that tag (all of
C. elegans, most of chicken and frog) it is the transcript with the longest
CDS, then the longest spliced length, then the smallest transcript ID; where
the annotation does tag one, that rule picks the same transcript for 99.4%
or more of genes in 11 of the 13 tagged species. The gene records the choice
in canonical_transcript_id and canonical_source, and that transcript is the
gene's only one with is_canonical true.

Connected to:
  - gtf_parser.py: consumes yielded records
  - biomart_parser.py: domain dicts are merged in after extraction
  - batch_writer.py: output dicts are written to Neo4j
"""

from typing import Dict, List, Tuple
from collections import Counter, defaultdict
import logging

logger = logging.getLogger(__name__)

CANONICAL_TAG = "Ensembl_canonical"

# canonical_source values: how a gene's canonical transcript was chosen
SOURCE_TAGGED = "Ensembl_canonical"          # tagged in the annotation
SOURCE_LONGEST_CDS = "longest_cds"           # no tag: longest CDS
SOURCE_LONGEST_TRANSCRIPT = "longest_transcript"  # no tag, no CDS: longest spliced


def _tags(attrs: Dict) -> List[str]:
    """A record's tag values: a list from Ensembl GTF, or a comma-separated
    string from a GFF3 file."""
    tags = attrs.get("tag", [])
    return tags.split(",") if isinstance(tags, str) else tags


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

    # Per-transcript sums, keyed by transcript_id
    tx_cds: Dict[str, int] = defaultdict(int)
    tx_utr5: Dict[str, int] = defaultdict(int)
    tx_utr3: Dict[str, int] = defaultdict(int)
    tx_exons: Dict[str, int] = defaultdict(int)
    tx_spliced: Dict[str, int] = defaultdict(int)   # summed exon lengths
    tagged_canonical = set()

    # Track feature rank per transcript+type
    feature_ranks: Dict[str, int] = defaultdict(int)

    for rec in records:
        attrs = rec["attributes"]
        f_type = rec["feature_type"]

        if f_type == "gene":
            gene_id = attrs.get("gene_id", "").strip()
            if not gene_id:
                continue
            genes[gene_id] = {
                "gene_id":      gene_id,
                "name":         attrs.get("gene_name", attrs.get("Name", gene_id)),
                "biotype":      attrs.get("gene_biotype", attrs.get("gene_type", "unknown")),
                "chromosome":   rec["chromosome"],
                "start":        rec["start"],
                "end":          rec["end"],
                "strand":       rec["strand"],
                "length":       rec["length"],
                "species_taxon": species_taxon,
                # These will be filled in below, from the canonical transcript
                "cds_length":   0,
                "exon_count":   0,
                "utr5_length":  0,
                "utr3_length":  0,
                "utr_cds_ratio": None,
                "canonical_transcript_id": None,
                "canonical_source": None,
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
                "cds_length":    0,
                "support_level": support_level,
                "is_canonical":  False,
            }
            if CANONICAL_TAG in _tags(attrs):
                tagged_canonical.add(transcript_id)

        elif f_type in ("CDS", "exon", "UTR", "five_prime_utr", "three_prime_utr",
                        "start_codon", "stop_codon"):
            transcript_id = attrs.get("transcript_id", "").strip()
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
            length = rec["length"]

            features.append({
                "feature_id":    feature_id,
                "transcript_id": transcript_id,
                "type":          normalised_type,
                "length":        length,
                "rank":          rank,
                "start":         rec["start"],
                "end":           rec["end"],
            })

            # Accumulate transcript-level sums
            if f_type == "CDS":
                tx_cds[transcript_id] += length
            elif f_type in ("UTR", "five_prime_utr"):
                tx_utr5[transcript_id] += length
            elif f_type == "three_prime_utr":
                tx_utr3[transcript_id] += length
            elif f_type == "exon":
                tx_exons[transcript_id] += 1
                tx_spliced[transcript_id] += length

    # Back-fill transcript values and group transcripts by gene
    gene_transcripts: Dict[str, List[str]] = defaultdict(list)
    for transcript_id, transcript in transcripts.items():
        transcript["exon_count"] = tx_exons.get(transcript_id, 0)
        transcript["cds_length"] = tx_cds.get(transcript_id, 0)
        gene_transcripts[transcript["gene_id"]].append(transcript_id)

    # Back-fill gene values from each gene's canonical transcript. A gene
    # without transcripts keeps 0 and None.
    sources: Counter = Counter()
    for gene_id, gene in genes.items():
        candidates = gene_transcripts.get(gene_id)
        if not candidates:
            continue
        tagged = [t for t in candidates if t in tagged_canonical]
        chosen = min(
            tagged or candidates,
            key=lambda t: (-tx_cds.get(t, 0), -tx_spliced.get(t, 0), t),
        )
        cds = tx_cds.get(chosen, 0)
        utr5 = tx_utr5.get(chosen, 0)
        utr3 = tx_utr3.get(chosen, 0)
        if tagged:
            source = SOURCE_TAGGED
        elif cds > 0:
            source = SOURCE_LONGEST_CDS
        else:
            source = SOURCE_LONGEST_TRANSCRIPT

        transcripts[chosen]["is_canonical"] = True
        gene["cds_length"] = cds
        gene["exon_count"] = tx_exons.get(chosen, 0)
        gene["utr5_length"] = utr5
        gene["utr3_length"] = utr3
        gene["utr_cds_ratio"] = round((utr5 + utr3) / cds, 4) if cds > 0 else None
        gene["canonical_transcript_id"] = chosen
        gene["canonical_source"] = source
        sources[source] += 1

    logger.info(
        "Extracted %d genes, %d transcripts, %d features for taxon %s",
        len(genes), len(transcripts), len(features), species_taxon,
    )
    logger.info(
        "Canonical transcripts for taxon %s: %d tagged %s, %d longest CDS, "
        "%d longest transcript, %d genes without transcripts",
        species_taxon, sources[SOURCE_TAGGED], CANONICAL_TAG,
        sources[SOURCE_LONGEST_CDS], sources[SOURCE_LONGEST_TRANSCRIPT],
        len(genes) - sum(sources.values()),
    )

    return list(genes.values()), list(transcripts.values()), features
