#!/usr/bin/env bash
# Download all 14 Ensembl GTF files (release 111) + BioMart TSV exports.
#
# Prerequisites:
#   - wget or curl installed
#   - Ensembl FTP accessible
#   - data/gtf/ and data/biomart/ directories exist (created here)
#
# Usage:
#   bash scripts/download_ensembl.sh

set -euo pipefail

ENSEMBL_RELEASE=111
ENSEMBL_BASE="https://ftp.ensembl.org/pub/release-${ENSEMBL_RELEASE}/gtf"
ENSEMBL_PLANTS_BASE="https://ftp.ensemblgenomes.ebi.ac.uk/pub/plants/release-${ENSEMBL_RELEASE}/gtf"
ENSEMBL_FUNGI_BASE="https://ftp.ensemblgenomes.ebi.ac.uk/pub/fungi/release-${ENSEMBL_RELEASE}/gtf"

GTF_DIR="${GTF_DATA_DIR:-./data/gtf}"
BIOMART_DIR="${BIOMART_DATA_DIR:-./data/biomart}"

mkdir -p "$GTF_DIR" "$BIOMART_DIR"

echo "=== Downloading Ensembl Release ${ENSEMBL_RELEASE} GTF files ==="

# ── Core Ensembl species ─────────────────────────────────────────────────────
declare -A CORE_SPECIES=(
    ["homo_sapiens"]="Homo_sapiens.GRCh38.${ENSEMBL_RELEASE}.gtf.gz"
    ["mus_musculus"]="Mus_musculus.GRCm39.${ENSEMBL_RELEASE}.gtf.gz"
    ["danio_rerio"]="Danio_rerio.GRCz11.${ENSEMBL_RELEASE}.gtf.gz"
    ["gallus_gallus"]="Gallus_gallus.bGalGal1.mat.broiler.GRCg7b.${ENSEMBL_RELEASE}.gtf.gz"
    ["octopus_bimaculoides"]="Octopus_bimaculoides.ASM119306v1.${ENSEMBL_RELEASE}.gtf.gz"
    ["pan_troglodytes"]="Pan_troglodytes.Pan_tro_3.0.${ENSEMBL_RELEASE}.gtf.gz"
    ["drosophila_melanogaster"]="Drosophila_melanogaster.BDGP6.46.${ENSEMBL_RELEASE}.gtf.gz"
    ["caenorhabditis_elegans"]="Caenorhabditis_elegans.WBcel235.${ENSEMBL_RELEASE}.gtf.gz"
)

for species_dir in "${!CORE_SPECIES[@]}"; do
    filename="${CORE_SPECIES[$species_dir]}"
    outfile="${GTF_DIR}/${species_dir}.gtf.gz"
    if [[ -f "$outfile" ]]; then
        echo "  ✓ $species_dir already downloaded"
        continue
    fi
    echo "  ↓ Downloading $species_dir..."
    wget -q -O "$outfile" \
        "${ENSEMBL_BASE}/${species_dir}/${filename}" \
        || { echo "  ✗ Failed to download $species_dir"; rm -f "$outfile"; }
done

# ── Ensembl Plants ────────────────────────────────────────────────────────────
declare -A PLANT_SPECIES=(
    ["arabidopsis_thaliana"]="Arabidopsis_thaliana.TAIR10.${ENSEMBL_RELEASE}.gtf.gz"
    ["oryza_sativa"]="Oryza_sativa.IRGSP-1.0.${ENSEMBL_RELEASE}.gtf.gz"
    ["physcomitrium_patens"]="Physcomitrium_patens.Phypa_V3.${ENSEMBL_RELEASE}.gtf.gz"
    ["chlamydomonas_reinhardtii"]="Chlamydomonas_reinhardtii.Chlamydomonas_reinhardtii_v5.5.${ENSEMBL_RELEASE}.gtf.gz"
)

for species_dir in "${!PLANT_SPECIES[@]}"; do
    filename="${PLANT_SPECIES[$species_dir]}"
    outfile="${GTF_DIR}/${species_dir}.gtf.gz"
    if [[ -f "$outfile" ]]; then
        echo "  ✓ $species_dir already downloaded"
        continue
    fi
    echo "  ↓ Downloading $species_dir (plants)..."
    wget -q -O "$outfile" \
        "${ENSEMBL_PLANTS_BASE}/${species_dir}/${filename}" \
        || { echo "  ✗ Failed to download $species_dir"; rm -f "$outfile"; }
done

# ── Ensembl Fungi ─────────────────────────────────────────────────────────────
declare -A FUNGI_SPECIES=(
    ["aspergillus_niger"]="Aspergillus_niger.ASM285v2.${ENSEMBL_RELEASE}.gtf.gz"
    ["saccharomyces_cerevisiae"]="Saccharomyces_cerevisiae.R64-1-1.${ENSEMBL_RELEASE}.gtf.gz"
)

for species_dir in "${!FUNGI_SPECIES[@]}"; do
    filename="${FUNGI_SPECIES[$species_dir]}"
    outfile="${GTF_DIR}/${species_dir}.gtf.gz"
    if [[ -f "$outfile" ]]; then
        echo "  ✓ $species_dir already downloaded"
        continue
    fi
    echo "  ↓ Downloading $species_dir (fungi)..."
    wget -q -O "$outfile" \
        "${ENSEMBL_FUNGI_BASE}/${species_dir}/${filename}" \
        || { echo "  ✗ Failed to download $species_dir"; rm -f "$outfile"; }
done

echo ""
echo "=== Download complete. Files in: $GTF_DIR ==="
echo "Next step: bash scripts/download_ecoli.sh"
echo "Then:      python -m app.ingestion.run_ingest --all"
