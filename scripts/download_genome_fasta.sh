#!/usr/bin/env bash
# Download genome FASTA for a given taxon ID.
# Supports all 17 Gene-Intel species.
#
# Usage:
#   bash scripts/download_genome_fasta.sh <taxon_id>
#   bash scripts/download_genome_fasta.sh 175781   # Octopus
#   bash scripts/download_genome_fasta.sh 8665     # King cobra
#
# Output: data/genomes/<taxon_id>.fa.gz

set -euo pipefail

TAXON_ID="${1:-}"
if [[ -z "$TAXON_ID" ]]; then
    echo "Usage: $0 <taxon_id>"
    echo ""
    echo "Available taxon IDs:"
    echo "  9606   — Human (Homo sapiens)"
    echo "  10090  — Mouse (Mus musculus)"
    echo "  7955   — Zebrafish (Danio rerio)"
    echo "  9031   — Chicken (Gallus gallus)"
    echo "  175781 — Octopus (Octopus bimaculoides)"
    echo "  9598   — Chimpanzee (Pan troglodytes)"
    echo "  7227   — Fruit fly (Drosophila melanogaster)"
    echo "  6239   — Roundworm (Caenorhabditis elegans)"
    echo "  3702   — Thale cress (Arabidopsis thaliana)"
    echo "  4530   — Rice (Oryza sativa)"
    echo "  3218   — Moss (Physcomitrium patens)"
    echo "  3055   — Green alga (Chlamydomonas reinhardtii)"
    echo "  162425 — Black mould (Aspergillus niger)"
    echo "  4932   — Yeast (Saccharomyces cerevisiae)"
    echo "  511145 — E. coli K-12 (Escherichia coli)"
    echo "  9913   — Cow (Bos taurus)"
    echo "  8665   — King cobra (Ophiophagus hannah)"
    exit 1
fi

OUT_DIR="${GENOME_DATA_DIR:-./data/genomes}"
mkdir -p "$OUT_DIR"
OUT_PATH="${OUT_DIR}/${TAXON_ID}.fa.gz"

ENSEMBL_MAIN="https://ftp.ensembl.org/pub/release-111/fasta"
ENSEMBL_PLANTS="https://ftp.ensemblgenomes.ebi.ac.uk/pub/plants/release-58/fasta"
ENSEMBL_FUNGI="https://ftp.ensemblgenomes.ebi.ac.uk/pub/fungi/release-58/fasta"
NCBI_BASE="https://ftp.ncbi.nlm.nih.gov/genomes/all"

download() {
    local url="$1"
    local outfile="$2"
    if [[ -f "$outfile" ]]; then
        echo "  ✓ Already downloaded: $(basename "$outfile")"
    else
        echo "  ↓ Downloading $(basename "$outfile")..."
        wget --continue -q --show-progress -O "$outfile" "$url" || {
            echo "  ✗ Failed: $url"
            rm -f "$outfile"
            exit 1
        }
    fi
}

case "$TAXON_ID" in
    9606)
        echo "Downloading Human (Homo sapiens) genome..."
        download \
            "${ENSEMBL_MAIN}/homo_sapiens/dna/Homo_sapiens.GRCh38.dna.toplevel.fa.gz" \
            "$OUT_PATH"
        ;;
    10090)
        echo "Downloading Mouse (Mus musculus) genome..."
        download \
            "${ENSEMBL_MAIN}/mus_musculus/dna/Mus_musculus.GRCm39.dna.toplevel.fa.gz" \
            "$OUT_PATH"
        ;;
    7955)
        echo "Downloading Zebrafish (Danio rerio) genome..."
        download \
            "${ENSEMBL_MAIN}/danio_rerio/dna/Danio_rerio.GRCz11.dna.toplevel.fa.gz" \
            "$OUT_PATH"
        ;;
    9031)
        echo "Downloading Chicken (Gallus gallus) genome..."
        download \
            "${ENSEMBL_MAIN}/gallus_gallus/dna/Gallus_gallus.bGalGal1.mat.broiler.GRCg7b.dna.toplevel.fa.gz" \
            "$OUT_PATH"
        ;;
    175781)
        echo "Downloading Octopus (Octopus bimaculoides) genome..."
        # Octopus genome from NCBI
        download \
            "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/001/194/135/GCF_001194135.1_Octopus_bimaculoides_2.0/GCF_001194135.1_Octopus_bimaculoides_2.0_genomic.fna.gz" \
            "$OUT_PATH"
        ;;
    9598)
        echo "Downloading Chimpanzee (Pan troglodytes) genome..."
        download \
            "${ENSEMBL_MAIN}/pan_troglodytes/dna/Pan_troglodytes.Pan_tro_3.0.dna.toplevel.fa.gz" \
            "$OUT_PATH"
        ;;
    7227)
        echo "Downloading Fruit fly (Drosophila melanogaster) genome..."
        download \
            "${ENSEMBL_MAIN}/drosophila_melanogaster/dna/Drosophila_melanogaster.BDGP6.46.dna.toplevel.fa.gz" \
            "$OUT_PATH"
        ;;
    6239)
        echo "Downloading Roundworm (Caenorhabditis elegans) genome..."
        download \
            "${ENSEMBL_MAIN}/caenorhabditis_elegans/dna/Caenorhabditis_elegans.WBcel235.dna.toplevel.fa.gz" \
            "$OUT_PATH"
        ;;
    3702)
        echo "Downloading Thale cress (Arabidopsis thaliana) genome..."
        download \
            "${ENSEMBL_PLANTS}/arabidopsis_thaliana/dna/Arabidopsis_thaliana.TAIR10.dna.toplevel.fa.gz" \
            "$OUT_PATH"
        ;;
    4530)
        echo "Downloading Rice (Oryza sativa) genome..."
        download \
            "${ENSEMBL_PLANTS}/oryza_sativa/dna/Oryza_sativa.IRGSP-1.0.dna.toplevel.fa.gz" \
            "$OUT_PATH"
        ;;
    3218)
        echo "Downloading Moss (Physcomitrium patens) genome..."
        download \
            "${ENSEMBL_PLANTS}/physcomitrium_patens/dna/Physcomitrium_patens.Phypa_V3.dna.toplevel.fa.gz" \
            "$OUT_PATH"
        ;;
    3055)
        echo "Downloading Green alga (Chlamydomonas reinhardtii) genome..."
        download \
            "${ENSEMBL_PLANTS}/chlamydomonas_reinhardtii/dna/Chlamydomonas_reinhardtii.Chlamydomonas_reinhardtii_v5.5.dna.toplevel.fa.gz" \
            "$OUT_PATH"
        ;;
    162425)
        echo "Downloading Black mould (Aspergillus niger) genome..."
        download \
            "${ENSEMBL_FUNGI}/aspergillus_niger/dna/Aspergillus_niger.ASM285v2.dna.toplevel.fa.gz" \
            "$OUT_PATH"
        ;;
    4932)
        echo "Downloading Yeast (Saccharomyces cerevisiae) genome..."
        download \
            "${ENSEMBL_FUNGI}/saccharomyces_cerevisiae/dna/Saccharomyces_cerevisiae.R64-1-1.dna.toplevel.fa.gz" \
            "$OUT_PATH"
        ;;
    511145)
        echo "Downloading E. coli K-12 genome..."
        download \
            "${NCBI_BASE}/GCF/000/005/845/GCF_000005845.2_ASM584v2/GCF_000005845.2_ASM584v2_genomic.fna.gz" \
            "$OUT_PATH"
        ;;
    9913)
        echo "Downloading Cow (Bos taurus) genome..."
        download \
            "${ENSEMBL_MAIN}/bos_taurus/dna/Bos_taurus.ARS-UCD1.3.dna.toplevel.fa.gz" \
            "$OUT_PATH"
        ;;
    8665)
        echo "Downloading King cobra (Ophiophagus hannah) genome..."
        download \
            "${ENSEMBL_MAIN}/ophiophagus_hannah/dna/Ophiophagus_hannah.OphHan1.0.dna.toplevel.fa.gz" \
            "$OUT_PATH"
        ;;
    *)
        echo "Unknown taxon ID: $TAXON_ID"
        echo "Run without arguments to see available taxon IDs."
        exit 1
        ;;
esac

echo ""
echo "=== Download complete ==="
FILE_SIZE=$(du -sh "$OUT_PATH" 2>/dev/null | cut -f1 || echo "unknown")
echo "File:    $OUT_PATH"
echo "Size:    $FILE_SIZE"
echo ""
echo "Next step: run InterProScan domain ingestion:"
echo "  python -m app.ingestion.run_ingest --species ${TAXON_ID} --domain-source interproscan"
