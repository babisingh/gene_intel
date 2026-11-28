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

E. coli comes from NCBI GFF3, which has no transcript rows for its
protein-coding genes: their CDS rows name the gene as Parent. Each protein
(the CDS rows that share one ID) becomes a transcript named by its
protein_id, with the parts Ensembl's GTF gives a yeast gene: one exon over
the whole CDS, the CDS rows, a start_codon and a stop_codon. A GFF3 CDS
includes the stop codon and a GTF CDS does not, so its last 3 bp leave the
CDS and become the stop_codon feature: cds_length is then 3 bp per amino
acid in every species. A CDS marked partial=true keeps all of its bases and
gets no codon features, as its ends may not be codons. The tRNA, rRNA and
ncRNA rows of the non-coding genes are transcripts with exons of their own.

Connected to:
  - gtf_parser.py: consumes yielded records
  - biomart_parser.py: domain dicts are merged in after extraction
  - batch_writer.py: output dicts are written to Neo4j
"""

from typing import Dict, List, Tuple
from collections import Counter, defaultdict
import logging

from app.ingestion.gtf_parser import GFF3_RNA_TYPES

logger = logging.getLogger(__name__)

CANONICAL_TAG = "Ensembl_canonical"

# canonical_source values: how a gene's canonical transcript was chosen
SOURCE_TAGGED = "Ensembl_canonical"          # tagged in the annotation
SOURCE_LONGEST_CDS = "longest_cds"           # no tag: longest CDS
SOURCE_LONGEST_TRANSCRIPT = "longest_transcript"  # no tag, no CDS: longest spliced

FEATURE_TYPES = frozenset({"CDS", "exon", "UTR", "five_prime_utr", "three_prime_utr",
                           "start_codon", "stop_codon"})
CODON_BP = 3

# (start, end) rows of one CDS, in transcription order
Segments = List[Tuple[int, int]]


def _tags(attrs: Dict) -> List[str]:
    """A record's tag values: a list from Ensembl GTF, or a comma-separated
    string from a GFF3 file."""
    tags = attrs.get("tag", [])
    return tags.split(",") if isinstance(tags, str) else tags


def _split_stop_codon(segments: Segments, strand: str) -> Tuple[Segments, Segments]:
    """Split the last 3 bases, the stop codon, off a CDS. Returns the CDS
    without them and the stop codon, both as rows in transcription order.
    A row's 3' end is its end on the plus strand, its start on the minus."""
    cds, stop = list(segments), []
    left = CODON_BP
    while left and cds:
        start, end = cds.pop()
        cut = min(left, end - start + 1)
        if strand == "-":
            stop.insert(0, (start, start + cut - 1))
            start += cut
        else:
            stop.insert(0, (end - cut + 1, end))
            end -= cut
        if start <= end:
            cds.append((start, end))
        left -= cut
    return cds, stop


def _start_codon(segments: Segments, strand: str) -> Segments:
    """The first 3 bases of a CDS, its start codon, as rows."""
    codon, left = [], CODON_BP
    for start, end in segments:
        cut = min(left, end - start + 1)
        codon.append((end - cut + 1, end) if strand == "-" else (start, start + cut - 1))
        left -= cut
        if not left:
            break
    return codon


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

    # GFF3 CDS rows that hang off their gene, keyed by (gene_id, CDS ID)
    gene_cds: Dict[Tuple[str, str], List[Dict]] = defaultdict(list)

    def add_feature(transcript_id: str, f_type: str, start: int, end: int) -> None:
        """Append one feature and add it to its transcript's sums."""
        # Normalise UTR type
        normalised_type = f_type
        if f_type in ("five_prime_utr", "three_prime_utr"):
            normalised_type = "UTR"

        rank_key = f"{transcript_id}_{normalised_type}"
        feature_ranks[rank_key] += 1
        rank = feature_ranks[rank_key]
        length = end - start + 1   # both ends count, as in gtf_parser.py

        features.append({
            "feature_id":    f"{transcript_id}_{normalised_type}_{rank}",
            "transcript_id": transcript_id,
            "type":          normalised_type,
            "length":        length,
            "rank":          rank,
            "start":         start,
            "end":           end,
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

        elif f_type == "transcript" or f_type in GFF3_RNA_TYPES:
            transcript_id = attrs.get("transcript_id", "").strip()
            gene_id = attrs.get("gene_id", "").strip()
            if not transcript_id or not gene_id:
                continue
            support_raw = attrs.get("transcript_support_level", None)
            support_level = None
            if support_raw and support_raw.isdigit():
                support_level = int(support_raw)
            # A GFF3 RNA row's type (tRNA, rRNA, ...) is its biotype
            default_type = "mRNA" if f_type == "transcript" else f_type
            transcripts[transcript_id] = {
                "transcript_id": transcript_id,
                "gene_id":       gene_id,
                "type":          attrs.get("transcript_biotype",
                                           attrs.get("transcript_type", default_type)),
                "exon_count":    0,
                "cds_length":    0,
                "support_level": support_level,
                "is_canonical":  False,
            }
            if CANONICAL_TAG in _tags(attrs):
                tagged_canonical.add(transcript_id)

        elif f_type in FEATURE_TYPES:
            transcript_id = attrs.get("transcript_id", "").strip()
            if transcript_id:
                add_feature(transcript_id, f_type, rec["start"], rec["end"])
            elif f_type == "CDS" and attrs.get("gene_id") and attrs.get("ID"):
                # GFF3: a bacterial CDS row, its Parent is the gene (below)
                gene_cds[(attrs["gene_id"], attrs["ID"])].append(rec)

    # Each protein of a GFF3 gene (its CDS rows: two when ribosomal slippage
    # joins two reading frames, as in prfB) becomes a transcript. A
    # pseudogene's CDS rows are left out: pseudogene rows are not loaded.
    for (gene_id, cds_id), rows in gene_cds.items():
        if gene_id not in genes:
            continue
        attrs = rows[0]["attributes"]
        strand = rows[0]["strand"]
        transcript_id = attrs.get("protein_id") or cds_id
        transcripts[transcript_id] = {
            "transcript_id": transcript_id,
            "gene_id":       gene_id,
            "type":          "protein_coding",
            "exon_count":    0,
            "cds_length":    0,
            "support_level": None,
            "is_canonical":  False,
        }
        segments = sorted(((r["start"], r["end"]) for r in rows),
                          reverse=(strand == "-"))
        add_feature(transcript_id, "exon",
                    min(start for start, _ in segments), max(end for _, end in segments))
        if attrs.get("partial") == "true":
            cds, start_codon, stop_codon = segments, [], []
        else:
            cds, stop_codon = _split_stop_codon(segments, strand)
            start_codon = _start_codon(segments, strand)
        for f_type, parts in (("CDS", cds), ("start_codon", start_codon),
                              ("stop_codon", stop_codon)):
            for start, end in parts:
                add_feature(transcript_id, f_type, start, end)

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
