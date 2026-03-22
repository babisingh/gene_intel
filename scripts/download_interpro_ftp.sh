#!/usr/bin/env bash
# Download the InterPro protein2ipr.dat.gz bulk file for offline domain ingestion.
#
# File size: ~5-7 GB compressed
# URL:  https://ftp.ebi.ac.uk/pub/databases/interpro/current_release/protein2ipr.dat.gz
#
# Prerequisites:
#   - wget installed
#   - ~10 GB free disk space
#
# Usage:
#   bash scripts/download_interpro_ftp.sh

set -euo pipefail

FTP_BASE="https://ftp.ebi.ac.uk/pub/databases/interpro/current_release"
OUT_DIR="${INTERPRO_FTP_DIR:-./data/interpro_ftp}"

mkdir -p "$OUT_DIR"

echo "=== Downloading InterPro protein2ipr.dat.gz ==="
echo "Target directory: $OUT_DIR"
echo ""

FILE="protein2ipr.dat.gz"
MD5_FILE="protein2ipr.dat.gz.md5"
OUT_PATH="${OUT_DIR}/${FILE}"
MD5_PATH="${OUT_DIR}/${MD5_FILE}"

# Download MD5 first
echo "Downloading MD5 checksum..."
wget -q -O "$MD5_PATH" "${FTP_BASE}/${MD5_FILE}" || {
    echo "WARNING: Could not download MD5 file — skipping checksum verification"
    MD5_PATH=""
}

# Download main file with --continue (resume support)
if [[ -f "$OUT_PATH" ]]; then
    echo "File already exists — resuming download if incomplete..."
fi

echo "Downloading ${FILE} (this may take 1-2 hours on a typical connection)..."
wget --continue \
     --progress=dot:giga \
     -O "$OUT_PATH" \
     "${FTP_BASE}/${FILE}" || {
    echo "Download failed — partial file retained for resumption."
    exit 1
}

# Verify MD5 checksum
if [[ -n "$MD5_PATH" && -f "$MD5_PATH" ]]; then
    echo ""
    echo "Verifying MD5 checksum..."
    EXPECTED_MD5=$(awk '{print $1}' "$MD5_PATH")
    ACTUAL_MD5=$(md5sum "$OUT_PATH" | awk '{print $1}')

    if [[ "$EXPECTED_MD5" == "$ACTUAL_MD5" ]]; then
        echo "  ✓ MD5 checksum verified"
    else
        echo "  ✗ MD5 mismatch!"
        echo "    Expected: $EXPECTED_MD5"
        echo "    Actual:   $ACTUAL_MD5"
        echo "  The file may be corrupted. Re-run this script to resume download."
        exit 1
    fi
else
    echo "MD5 verification skipped."
fi

# Print file size
FILE_SIZE=$(du -sh "$OUT_PATH" | cut -f1)
echo ""
echo "=== Download complete ==="
echo "File:    $OUT_PATH"
echo "Size:    $FILE_SIZE"
echo ""
echo "Next step: run FTP domain ingestion:"
echo "  python scripts/ingest_domains_ftp.py --ftp-file $OUT_PATH"
