# Gene-Intel Discovery Engine v2.0

Semantic genomic graph search across **17 species** — ask questions in plain English, get interactive gene networks.

## Core Concept

Genes are matched not by DNA sequence but by **structural architecture** — the arrangement of Exon/UTR/CDS features and proximity to neighbouring genes within 10 kilobases. This surfaces "Functional Twins" that BLAST sequence alignment misses.

## Quick Start

### 1. Prerequisites

- Python 3.11+
- Node.js 20+
- Neo4j AuraDB account (free tier at [console.neo4j.io](https://console.neo4j.io))
- Anthropic API key

### 2. Backend Setup

```bash
# Clone and set up Python environment
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Neo4j AuraDB credentials and Anthropic API key

# Initialise Neo4j schema (run once)
python scripts/init_schema.py
```

### 3. Load Demo Data (Human + Zebrafish, ~5 min)

```bash
# Download GTF files
bash scripts/download_ensembl.sh    # downloads all 14 Ensembl species
bash scripts/download_ecoli.sh      # downloads E. coli GFF3

# Quick demo seed (Human + Zebrafish only)
python scripts/seed_demo.py

# Or ingest all 15 species (run overnight ~2 hours)
python -m app.ingestion.run_ingest --all
```

### 4. Start Backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### 5. Start Frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

## The 17 Species

| # | Common Name | Scientific Name | Taxon ID | Kingdom |
|---|------------|-----------------|----------|---------|
| 1 | Human | Homo sapiens | 9606 | Animalia |
| 2 | Mouse | Mus musculus | 10090 | Animalia |
| 3 | Zebrafish | Danio rerio | 7955 | Animalia |
| 4 | Chicken | Gallus gallus | 9031 | Animalia |
| 5 | Octopus | Octopus bimaculoides | 175781 | Animalia |
| 6 | Chimpanzee | Pan troglodytes | 9598 | Animalia |
| 7 | Fruit fly | Drosophila melanogaster | 7227 | Invertebrata |
| 8 | Roundworm | C. elegans | 6239 | Invertebrata |
| 9 | Thale cress | Arabidopsis thaliana | 3702 | Plantae |
| 10 | Rice | Oryza sativa | 4530 | Plantae |
| 11 | Moss | Physcomitrium patens | 3218 | Bryophyta |
| 12 | Green alga | Chlamydomonas reinhardtii | 3055 | Algae |
| 13 | Black mould | Aspergillus niger | 162425 | Fungi |
| 14 | Yeast | S. cerevisiae | 4932 | Fungi |
| 15 | E. coli K-12 | Escherichia coli | 511145 | Bacteria |
| 16 | Cow | Bos taurus | 9913 | Animalia |
| 17 | King cobra | Ophiophagus hannah | 8665 | Reptilia |

## Domain Data

Gene-Intel uses a 4-route fallback strategy to source protein domain annotations, replacing the deprecated BioMart API:

| Route | Source | Coverage | Use case |
|-------|--------|----------|----------|
| 1 | UniProt REST API | Swiss-Prot reviewed proteins | Model organisms (default) |
| 2 | InterPro REST API | Pfam + CDD + SMART | Enrichment, e-values |
| 3 | EMBL-EBI FTP bulk | All UniProtKB matches | Production offline ingestion |
| 4 | InterProScan | Computed from sequence | Non-model organisms |

Quick command reference:

```bash
# Run domain ingestion after GTF load (default: UniProt + InterPro)
python -m app.ingestion.run_ingest --species 9606 --step domains

# Check domain coverage
python -m app.ingestion.run_ingest domains --report

# Run InterProScan for a non-model organism (requires genome FASTA)
python -m app.ingestion.run_ingest --species 175781 --domain-source interproscan
```

## Architecture

```
User Query (NL)
      │
      ▼
Agent A (Claude claude-sonnet-4-5)
  — NL → Cypher via Bio-Dictionary
      │
      ▼
Cypher Validator (whitelist check)
      │
      ▼
Neo4j AuraDB (graph query)
      │
      ▼
Agent C (Claude claude-sonnet-4-5)
  — Results → Persona-aware explanation
      │
      ▼
SearchResponse (nodes + edges + explanation)
      │
      ▼
Sigma.js v3 (WebGL graph, max 300 nodes)
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/search` | NL query → graph results + explanation |
| GET | `/api/species` | All loaded species with gene counts |
| GET | `/api/gene/{gene_id}` | Full gene detail for locus diagram |
| GET | `/api/neighborhood/{gene_id}` | CO_LOCATED_WITH neighbours |
| GET | `/api/health` | Neo4j + LLM status check |

## Running Tests

```bash
cd backend
pytest tests/ -v
```

## Key Commands Reference

```bash
# One-time schema init
python scripts/init_schema.py

# Ingest a single species
python -m app.ingestion.run_ingest --species 9606

# Ingest E. coli (GFF3 auto-detected)
python -m app.ingestion.run_ingest --species 511145

# Ingest all 17 species
python -m app.ingestion.run_ingest --all

# Run backend
uvicorn app.main:app --reload --port 8000

# Run frontend
cd frontend && npm install && npm run dev

# Run tests
pytest backend/tests/ -v
```

## Personas

- **Investor**: Plain English, drug target relevance, market framing
- **Student** (default): Scientific terms defined inline, educational tone
- **Researcher**: Full technical detail, gene IDs, domain accessions, Cypher query shown

## Sample Queries

- *"Find drug-like peptides co-located with cutting enzymes across all species"*
- *"Compare kinase genes between human and chimpanzee"*
- *"Which octopus genes show complex splicing near neurotransmitter domains?"*
- *"Find functional twins of GLP-1 with glucagon domains near a protease in all species"*
- *"Compare photosynthesis genes between green alga, moss and rice"*
