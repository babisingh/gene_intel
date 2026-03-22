"""
BioMart TSV domain parser.

BioMart exports a TSV with columns:
  Gene stable ID | Pfam domain | InterPro ID | GO term accession | ...

This parser reads those TSVs and produces {gene_id, domain_id, source, description}
dicts for batch_writer.write_domains_batch().

E. coli domains come from GFF3 Dbxref — this module is NOT used for E. coli.

Connected to:
  - run_ingest.py: called per species after feature extraction
  - batch_writer.py: domain dicts passed to write_domains_batch()
"""

import csv
import os
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

# BioMart column headers we recognise.
# The exact header string varies by Ensembl release and mirror, so we list
# all known aliases. The tuple is (source_label, internal_key).
DOMAIN_COLUMNS = {
    # Pfam — header varies by release ("Pfam domain" older, "Pfam ID" newer)
    "Pfam domain":                ("Pfam",     "pfam_id"),
    "Pfam domain ID":             ("Pfam",     "pfam_id"),
    "Pfam ID":                    ("Pfam",     "pfam_id"),
    # PANTHER
    "PANTHER ID":                 ("PANTHER",  "panther_id"),
    # InterPro — same header-variation issue
    "InterPro accession":         ("InterPro", "interpro_id"),
    "InterPro ID":                ("InterPro", "interpro_id"),
    "Interpro ID":                ("InterPro", "interpro_id"),   # lower-case 'r'
    # GO
    "GO term accession":          ("GO",       "go_id"),
    # KEGG
    "KEGG Pathway and Enzyme ID": ("KEGG",     "kegg_id"),
}

GENE_ID_COLUMNS = {
    "Gene stable ID",
    "Ensembl Gene ID",
}


def parse_biomart_tsv(filepath: str) -> List[Dict]:
    """
    Parse a BioMart TSV file and return domain association dicts.
    Each dict: {gene_id, domain_id, source, description}
    """
    if not os.path.exists(filepath):
        logger.warning("BioMart TSV not found: %s", filepath)
        return []

    # Guard: detect BioMart server error responses stored as the file content
    try:
        with open(filepath, encoding="utf-8") as _f:
            first_line = _f.readline()
        if "Query ERROR" in first_line or "BioMart::Exception" in first_line or "Could not connect" in first_line:
            logger.warning(
                "BioMart file %s contains a server error (BioMart API down). "
                "Skipping — use --step domains --domain-source uniprot instead.",
                filepath,
            )
            return []
    except OSError:
        pass

    results = []
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        headers = reader.fieldnames or []

        # Find the gene_id column
        gene_col = next((h for h in headers if h in GENE_ID_COLUMNS), None)
        if not gene_col:
            logger.warning("No gene ID column found in %s. Headers: %s", filepath, headers)
            return []

        # Identify which domain columns are present
        active_domain_cols = {
            col: info
            for col, info in DOMAIN_COLUMNS.items()
            if col in headers
        }

        for row in reader:
            gene_id = row.get(gene_col, "").strip()
            if not gene_id:
                continue

            for col, (source, _) in active_domain_cols.items():
                raw_val = row.get(col, "").strip()
                if not raw_val:
                    continue
                # Some cells contain multiple values separated by semicolons
                for val in raw_val.split(";"):
                    val = val.strip()
                    if not val:
                        continue
                    # GO values already carry the "GO:" prefix (e.g. "GO:0016531").
                    # All other sources (Pfam, InterPro …) provide bare IDs.
                    if source == "GO" and val.upper().startswith("GO:"):
                        domain_id = val
                    else:
                        domain_id = f"{source}:{val}"
                    results.append({
                        "gene_id":     gene_id,
                        "domain_id":   domain_id,
                        "source":      source,
                        "description": "",  # BioMart TSVs rarely include descriptions
                    })

    logger.info("Parsed %d domain associations from %s", len(results), filepath)
    return results


def extract_domains_from_gff3_attrs(gene_id: str, db_xrefs: List[str]) -> List[Dict]:
    """
    Extract domain dicts from NCBI GFF3 Dbxref values.
    Used for E. coli where BioMart is not available.

    db_xrefs example: ["UniProtKB/Swiss-Prot:P0AD86", "Pfam:PF01030"]
    """
    results = []
    for xref in db_xrefs:
        xref = xref.strip()
        if ":" not in xref:
            continue
        prefix = xref.split(":")[0]
        source = _normalise_source(prefix)
        if source:
            results.append({
                "gene_id":     gene_id,
                "domain_id":   xref,
                "source":      source,
                "description": "",
            })
    return results


def _normalise_source(prefix: str) -> str:
    mapping = {
        "Pfam":                 "Pfam",
        "InterPro":             "InterPro",
        "GO":                   "GO",
        "KEGG":                 "KEGG",
        "UniProtKB/Swiss-Prot": "UniProt",
        "UniProtKB":            "UniProt",
        "RefSeq":               "",          # Not a domain — skip
        "GeneID":               "",          # Not a domain — skip
    }
    return mapping.get(prefix, "")
