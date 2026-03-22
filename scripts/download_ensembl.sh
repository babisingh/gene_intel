#!/usr/bin/env bash
# Download all GTF/GFF3 annotation files for Gene-Intel (Ensembl release 111).
#
# Prerequisites:
#   - wget installed
#   - data/gtf/ and data/biomart/ directories exist (created here)
#
# Usage:
#   bash scripts/download_ensembl.sh

set -euo pipefail

GTF_DIR="${GTF_DATA_DIR:-./data/gtf}"
BIOMART_DIR="${BIOMART_DATA_DIR:-./data/biomart}"

mkdir -p "$GTF_DIR" "$BIOMART_DIR"

echo "=== Downloading Ensembl Release 111 GTF files ==="

# Helper: skip download if file already exists
download() {
    local url="$1"
    local outfile="$2"
    if [[ -f "$outfile" ]]; then
        echo "  ✓ $(basename "$outfile") already downloaded"
    else
        echo "  ↓ Downloading $(basename "$outfile")..."
        wget -q -O "$outfile" "$url" || { echo "  ✗ Failed: $url"; rm -f "$outfile"; }
    fi
}

# ── Core Ensembl species ─────────────────────────────────────────────────────

download \
    "https://ftp.ensembl.org/pub/release-111/gtf/homo_sapiens/Homo_sapiens.GRCh38.111.gtf.gz" \
    "${GTF_DIR}/homo_sapiens.gtf.gz"

download \
    "https://ftp.ensembl.org/pub/release-111/gtf/mus_musculus/Mus_musculus.GRCm39.111.gtf.gz" \
    "${GTF_DIR}/mus_musculus.gtf.gz"

download \
    "https://ftp.ensembl.org/pub/release-111/gtf/danio_rerio/Danio_rerio.GRCz11.111.gtf.gz" \
    "${GTF_DIR}/danio_rerio.gtf.gz"

download \
    "https://ftp.ensembl.org/pub/release-111/gtf/gallus_gallus/Gallus_gallus.bGalGal1.mat.broiler.GRCg7b.111.gtf.gz" \
    "${GTF_DIR}/gallus_gallus.gtf.gz"

download \
    "https://ftp.ensembl.org/pub/release-111/gtf/xenopus_tropicalis/Xenopus_tropicalis.UCB_Xtro_10.0.111.gtf.gz" \
    "${GTF_DIR}/xenopus_tropicalis.gtf.gz"

download \
    "https://ftp.ensembl.org/pub/release-111/gtf/pan_troglodytes/Pan_troglodytes.Pan_tro_3.0.111.gtf.gz" \
    "${GTF_DIR}/pan_troglodytes.gtf.gz"

download \
    "https://ftp.ensembl.org/pub/release-111/gtf/drosophila_melanogaster/Drosophila_melanogaster.BDGP6.46.111.gtf.gz" \
    "${GTF_DIR}/drosophila_melanogaster.gtf.gz"

download \
    "https://ftp.ensembl.org/pub/release-111/gtf/caenorhabditis_elegans/Caenorhabditis_elegans.WBcel235.111.gtf.gz" \
    "${GTF_DIR}/caenorhabditis_elegans.gtf.gz"

# ── Ensembl Plants (release 58 = Ensembl 111 equivalent) ─────────────────────

download \
    "https://ftp.ensemblgenomes.ebi.ac.uk/pub/plants/release-58/gtf/arabidopsis_thaliana/Arabidopsis_thaliana.TAIR10.58.gtf.gz" \
    "${GTF_DIR}/arabidopsis_thaliana.gtf.gz"

download \
    "https://ftp.ensemblgenomes.ebi.ac.uk/pub/plants/release-58/gtf/oryza_sativa/Oryza_sativa.IRGSP-1.0.58.gtf.gz" \
    "${GTF_DIR}/oryza_sativa.gtf.gz"

download \
    "https://ftp.ensemblgenomes.ebi.ac.uk/pub/plants/release-58/gtf/physcomitrium_patens/Physcomitrium_patens.Phypa_V3.58.gtf.gz" \
    "${GTF_DIR}/physcomitrium_patens.gtf.gz"

download \
    "https://ftp.ensemblgenomes.ebi.ac.uk/pub/plants/release-58/gtf/chlamydomonas_reinhardtii/Chlamydomonas_reinhardtii.Chlamydomonas_reinhardtii_v5.5.58.gtf.gz" \
    "${GTF_DIR}/chlamydomonas_reinhardtii.gtf.gz"

# ── Ensembl Fungi (release 58 = Ensembl 111 equivalent) ──────────────────────

download \
    "https://ftp.ensemblgenomes.ebi.ac.uk/pub/fungi/release-58/gtf/aspergillus_niger/Aspergillus_niger.ASM285v2.58.gtf.gz" \
    "${GTF_DIR}/aspergillus_niger.gtf.gz"

download \
    "https://ftp.ensemblgenomes.ebi.ac.uk/pub/fungi/release-58/gtf/saccharomyces_cerevisiae/Saccharomyces_cerevisiae.R64-1-1.58.gtf.gz" \
    "${GTF_DIR}/saccharomyces_cerevisiae.gtf.gz"

# ── NCBI — E. coli K-12 (GFF3) ───────────────────────────────────────────────

download \
    "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/005/845/GCF_000005845.2_ASM584v2/GCF_000005845.2_ASM584v2_genomic.gff.gz" \
    "${GTF_DIR}/ecoli_k12.gff3.gz"

# ── Species 16-17 (added 2025) ────────────────────────────────────────────────

# Cow (Bos taurus) — Ensembl main (ARS-UCD1.3 assembly)
download \
    "https://ftp.ensembl.org/pub/release-111/gtf/bos_taurus/Bos_taurus.ARS-UCD1.3.111.gtf.gz" \
    "${GTF_DIR}/bos_taurus.gtf.gz"

# King cobra (Ophiophagus hannah) — Ensembl main (OphHan1.0 assembly)
download \
    "https://ftp.ensembl.org/pub/release-111/gtf/ophiophagus_hannah/Ophiophagus_hannah.OphHan1.0.111.gtf.gz" \
    "${GTF_DIR}/ophiophagus_hannah.gtf.gz"

echo ""
echo "=== Download complete. Files in: $GTF_DIR ==="
echo "Next step: python scripts/seed_demo.py"
echo "Or full ingest: cd backend && python -m app.ingestion.run_ingest --all"
