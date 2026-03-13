# Data Directory

This directory holds large genomic data files that are **not tracked by git**.

## Structure

```
data/
├── gtf/          # Raw GTF/GFF3 files (~20GB total for all 15 species)
└── biomart/      # BioMart TSV domain exports per species
```

## Downloading Data

### All 14 Ensembl species + BioMart TSVs:
```bash
bash scripts/download_ensembl.sh
```

### E. coli GFF3 from NCBI:
```bash
bash scripts/download_ecoli.sh
```

### Quick demo (Human + Zebrafish only):
```bash
python scripts/seed_demo.py
```

## File Naming Convention

- GTF files: `{scientific_name_underscored}.gtf.gz`
  - Example: `homo_sapiens.gtf.gz`
- BioMart TSVs: `biomart_{taxon_id}.tsv`
  - Example: `biomart_9606.tsv`
- E. coli GFF3: `ecoli_k12.gff3.gz`
