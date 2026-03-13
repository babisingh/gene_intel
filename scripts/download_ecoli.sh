#!/usr/bin/env bash
# Download E. coli K-12 GFF3 from NCBI RefSeq.
#
# Source: NCBI RefSeq assembly ASM584v2 (Escherichia coli str. K-12 substr. MG1655)
# Taxon ID: 511145
#
# Usage:
#   bash scripts/download_ecoli.sh

set -euo pipefail

GTF_DIR="${GTF_DATA_DIR:-./data/gtf}"
mkdir -p "$GTF_DIR"

NCBI_URL="https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/005/845/GCF_000005845.2_ASM584v2/GCF_000005845.2_ASM584v2_genomic.gff.gz"
OUTFILE="${GTF_DIR}/ecoli_k12.gff3.gz"

if [[ -f "$OUTFILE" ]]; then
    echo "✓ E. coli GFF3 already downloaded: $OUTFILE"
    exit 0
fi

echo "↓ Downloading E. coli K-12 GFF3 from NCBI..."
wget -q -O "$OUTFILE" "$NCBI_URL" \
    || { echo "✗ Download failed"; rm -f "$OUTFILE"; exit 1; }

echo "✓ Downloaded: $OUTFILE"
echo "Next step: python -m app.ingestion.run_ingest --species 511145"
