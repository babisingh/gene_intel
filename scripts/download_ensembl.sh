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

#ENSEMBL_RELEASE=111 #hardcoded to current dir 
ENSEMBL_BASE="https://ftp.ensembl.org/pub/current/gtf"
ENSEMBL_PLANTS_BASE="https://ftp.ensemblgenomes.ebi.ac.uk/pub/plants/current/gtf"
ENSEMBL_FUNGI_BASE="https://ftp.ensemblgenomes.ebi.ac.uk/pub/fungi/current/gtf"

GTF_DIR="${GTF_DATA_DIR:-./data/gtf}"
BIOMART_DIR="${BIOMART_DATA_DIR:-./data/biomart}"

mkdir -p "$GTF_DIR" "$BIOMART_DIR"

echo "=== Downloading Ensembl Release - Current - GTF files ==="

# ── Core Ensembl species ─────────────────────────────────────────────────────
declare -A CORE_SPECIES=(
    ["homo_sapiens"]="Homo_sapiens.GRCh38.115.gtf.gz"
    ["mus_musculus"]="Mus_musculus.GRCm39.115.gtf.gz"
    ["danio_rerio"]="Danio_rerio.GRCz11.115.gtf.gz"
    ["gallus_gallus"]="Gallus_gallus.bGalGal1.mat.broiler.GRCg7b.115.gtf.gz"
    ["xenopus_tropicalis"]="Xenopus_tropicalis.UCB_Xtro_10.0.115.gtf.gz"
    ["pan_troglodytes"]="Pan_troglodytes.Pan_tro_3.0.115.gtf.gz"
    ["drosophila_melanogaster"]="Drosophila_melanogaster.BDGP6.54.115.gtf.gz"
    ["caenorhabditis_elegans"]="Caenorhabditis_elegans.WBcel235.115.gtf.gz"
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
    ["arabidopsis_thaliana"]="Arabidopsis_thaliana.TAIR10.62.gtf.gz"
    ["oryza_sativa"]="Oryza_sativa.IRGSP-1.0.62.gtf.gz"
    ["physcomitrium_patens"]="Physcomitrium_patens.Phypa_V3.62.gtf.gz"
    ["chlamydomonas_reinhardtii"]="Chlamydomonas_reinhardtii.Chlamydomonas_reinhardtii_v5.5.62.gtf.gz"
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
    ["aspergillus_niger"]="Aspergillus_niger.ASM285v2.62.gtf.gz"
    ["saccharomyces_cerevisiae"]="Saccharomyces_cerevisiae.R64-1-1.62.gtf.gz"
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
