"""
Detects GTF dialect from the first 50 non-comment lines.

Why this matters:
  - Ensembl GTF column 9: gene_id "ENSG..."; gene_name "BRCA2"; db_xref "Pfam:PF00082"
  - NCBI GFF3 column 9:   ID=gene-b0001;Name=thrL;Dbxref=UniProtKB/Swiss-Prot:P0AD86

Returns: "ensembl_gtf" | "ncbi_gff3"

Connected to: gtf_parser.py (selects parsing strategy based on returned dialect)
"""

import re
import gzip


def detect_dialect(filepath: str) -> str:
    opener = gzip.open if filepath.endswith(".gz") else open
    lines_checked = 0
    with opener(filepath, "rt") as f:
        for line in f:
            if line.startswith("#"):
                # GFF3 files begin with ##gff-version 3
                if "gff-version 3" in line:
                    return "ncbi_gff3"
                continue
            parts = line.split("\t")
            if len(parts) < 9:
                continue
            col9 = parts[8]
            # Ensembl GTF uses key "value"; format
            if re.search(r'gene_id\s+"', col9):
                return "ensembl_gtf"
            # NCBI GFF3 uses key=value format
            if re.search(r'ID=gene-', col9):
                return "ncbi_gff3"
            lines_checked += 1
            if lines_checked >= 50:
                break
    return "ensembl_gtf"  # safe default
