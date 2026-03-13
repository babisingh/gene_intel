"""
Streaming GTF/GFF3 parser.

Reads the file line by line — never loads the full file into memory.
Human GTF is ~1.4GB uncompressed; streaming is non-negotiable.

Yields: dict with keys matching the :Gene/:Transcript/:Feature schema
        (see graph_models.py for the full shape)

Connected to:
  - dialect_detector.py: determines which parse_col9() strategy to use
  - feature_extractor.py: consumes yielded records to build graph node dicts
"""

import gzip
from typing import Generator, Dict


RELEVANT_FEATURE_TYPES = frozenset({
    "gene", "transcript", "CDS", "exon",
    "UTR", "five_prime_utr", "three_prime_utr",
    "start_codon", "stop_codon",
})


def parse_gtf_streaming(filepath: str, dialect: str) -> Generator[Dict, None, None]:
    """
    Yields one parsed record per GTF/GFF3 line.
    Handles both .gtf and .gtf.gz files transparently.
    """
    opener = gzip.open if filepath.endswith(".gz") else open
    with opener(filepath, "rt") as f:
        for line in f:
            if line.startswith("#") or line.strip() == "":
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 9:
                continue

            chrom, source, f_type, start, end, score, strand, frame, col9 = parts

            # Only process feature types we care about
            if f_type not in RELEVANT_FEATURE_TYPES:
                continue

            attrs = (
                parse_ensembl_col9(col9)
                if dialect == "ensembl_gtf"
                else parse_ncbi_col9(col9)
            )

            yield {
                "feature_type": f_type,
                "chromosome":   chrom,
                "start":        int(start),
                "end":          int(end),
                "strand":       strand,
                "attributes":   attrs,
                # length is always end - start in GTF (0-based half-open)
                "length":       int(end) - int(start),
            }


def parse_ensembl_col9(col9: str) -> Dict:
    """
    Parses Ensembl GTF attribute string.
    Example: gene_id "ENSG00000139618"; gene_name "BRCA2"; db_xref "Pfam:PF00082";
    """
    attrs: Dict = {}
    for field in col9.split(";"):
        field = field.strip()
        if not field:
            continue
        parts = field.split(" ", 1)
        if len(parts) == 2:
            key = parts[0]
            val = parts[1].strip('"')
            # db_xref can appear multiple times — collect as list
            if key == "db_xref":
                attrs.setdefault("db_xref", []).append(val)
            else:
                attrs[key] = val
    return attrs


def parse_ncbi_col9(col9: str) -> Dict:
    """
    Parses NCBI GFF3 attribute string.
    Example: ID=gene-b0001;Name=thrL;Dbxref=UniProtKB/Swiss-Prot:P0AD86,Pfam:PF01030
    """
    attrs: Dict = {}
    for field in col9.split(";"):
        field = field.strip()
        if "=" not in field:
            continue
        key, val = field.split("=", 1)
        if key == "Dbxref":
            attrs["db_xref"] = val.split(",")
        elif key == "ID" and val.startswith("gene-"):
            attrs["gene_id"] = val.replace("gene-", "")
        elif key == "Name":
            attrs["gene_name"] = val
        else:
            attrs[key] = val
    return attrs
