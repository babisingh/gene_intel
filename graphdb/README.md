# Graph database image

Neo4j Community 5.26 with the full 15-species Gene-Intel graph built into the
image. Railway runs it as the `neo4j` service in the `gene-intel` project, and
the web app reaches it over Railway's private network.

## Why the data is in the image

The app only reads the graph, and the graph is fully derived from the GTF files
in `backend/data/gtf` and the protein domain files in `graphdb/domains`.
Building it into the image means no volume (Railway
Hobby caps volumes at 5 GB, and this store is larger), nothing to back up, and
every build starts from a known state. A restart simply starts the same image
again.

## How the image is built

`graphdb/Dockerfile` has three stages:

1. `export_csv.py` runs the loader's own `ingest_species()` for every species
   in `SPECIES_REGISTRY`, with the Neo4j batch writers replaced by CSV
   writers. The result is the same graph that
   `python -m app.ingestion.run_ingest --all --step gtf` writes over Bolt,
   plus the protein domains from `graphdb/domains` (see below).
2. `build_db.sh` bulk-imports the CSVs with `neo4j-admin database import`,
   starts a temporary local server to create the constraints and indexes from
   `app/db/schema.py`, checks every node and relationship count against the
   export's manifest, then stops the server and removes the build-time system
   database so the runtime container starts fresh.
3. The runtime stage copies the store to `/graph`.

Size of the full graph: 15.8 million nodes and 18.5 million relationships
(461,444 genes, 978,774 transcripts, 14.3 million exon/CDS/UTR/codon
features, 41,077 protein domains, 1.3 million HAS_DOMAIN and 1.5 million
CO_LOCATED_WITH edges). Cow and King cobra are in the registry but have no
GTF file, so they are skipped, as the loader does.

## Protein domains

`graphdb/domains` holds the protein domains of the genes, as Pfam and
InterPro accessions. `export_csv.py` turns them into `Domain` nodes, each
shared by every gene that has the domain in any species, and `HAS_DOMAIN`
edges. A `Domain` node has `domain_id` (source and accession, such as
`Pfam:PF00069` or `InterPro:IPR000719`), `source` and `description`. The
build reads the committed files and fetches nothing.

The folder has one gzipped TSV per species (`<taxon>.tsv.gz`, with columns
`gene_id`, `source` and `accession`), the descriptions (`names.tsv.gz`) and
`sources.json`, which records what each file was made from, its row count
and checksum, and the GTF file it was made for. `fetch_domains.py` writes
them from sources that match the GTF files:

- Ensembl 111 and Ensembl Genomes 58 core databases, from their table dumps
  on the Ensembl FTP sites: each translation's Pfam hits, and the InterPro
  entries the database maps its member signatures to. A gene gets the
  domains of all its translations. Rice comes from Ensembl Plants 63, as
  its release 58 database has Pfam hits for almost no genes. Genes on
  patches and haplotypes are not in the GTF files and are left out.
- E. coli: UniProt's reference proteome UP000000625, matched to the GFF3's
  genes by b-number. UniProt also lists 95 b-numbers that are pseudogenes
  in the GFF3 and 18 that it does not have; they are left out.
- Descriptions: Pfam and InterPro, newest release first, then older
  releases, which still name entries retired since. 15 of the 41,077
  domains are in none of them and have an empty description.

| Species | Protein-coding genes | With a Pfam domain | With an InterPro entry |
|---|---:|---:|---:|
| Human | 20,073 | 91.9% | 96.2% |
| Mouse | 21,691 | 92.4% | 96.7% |
| Zebrafish | 25,432 | 89.9% | 94.9% |
| Chicken | 17,007 | 90.6% | 95.6% |
| Western clawed frog | 22,102 | 89.4% | 94.7% |
| Chimpanzee | 23,302 | 87.6% | 92.5% |
| Fruit fly | 13,986 | 77.7% | 82.6% |
| Roundworm | 19,985 | 67.3% | 73.8% |
| Thale cress | 27,628 | 79.0% | 85.1% |
| Rice | 35,804 | 63.6% | 69.2% |
| Moss | 32,234 | 56.6% | 63.8% |
| Green alga | 17,743 | 54.9% | 65.7% |
| Black mould | 13,872 | 61.5% | 66.4% |
| Yeast | 6,600 | 73.9% | 78.3% |
| E. coli K-12 | 4,290 | 95.8% | 96.9% |

To refresh the files, for example after replacing a GTF file, first change
the release in `fetch_domains.py` to match, then run from the repo root:

```bash
python3 graphdb/fetch_domains.py
```

It needs only the Python standard library, downloads about 260 MB (8.5
minutes in November 2026) and rewrites the folder. Commit the changes, then
rebuild the image. `graphdb/tests/test_domain_files.py` fails while a GTF
file differs from the one its domain file was made for.

The loader's own domain step (`python -m app.ingestion.run_ingest --step
domains`) is not used: its UniProt route stops after the first page of
results and writes one Domain node per gene and position, which the app
does not expect. The loader over Bolt does not read `graphdb/domains`.

## Deploying and rebuilding

```bash
graphdb/deploy.sh <railway project id>
```

The `neo4j` service is not connected to GitHub, and must not be: its
Dockerfile path setting is `Dockerfile`, so built from GitHub it would build
the repository's root `Dockerfile`, which is the web app. Instead `deploy.sh`
uploads only this Dockerfile with `railway up`, with `GENE_INTEL_SHA` set to
the current commit, and the build fetches the code and GTF files from GitHub
at that commit (Railway's upload limit is smaller than the GTF files). Push
first, then rerun it after changing the GTF files, the ingestion code,
`app/db/schema.py` or `graphdb/domains`. Pushes alone do not rebuild the
graph.

## Railway settings

`neo4j` service:

- Service settings: Dockerfile path `Dockerfile`, healthcheck path `/` with a
  600 second timeout, restart on failure. No volume, no public domain.
- `GRAPH_DB_PASSWORD`: a generated secret. It must not start with `NEO4J_`:
  the image turns every `NEO4J_*` variable into a Neo4j setting, and an
  unknown setting stops the server.
- `NEO4J_AUTH`: `neo4j/${{GRAPH_DB_PASSWORD}}`
- `PORT`: `7474`, used only by the healthcheck.
- Anonymous usage reporting to Neo4j is turned off
  (`NEO4J_dbms_usage__report_enabled=false`).
- Memory defaults (heap 512m, page cache 768m) are set in the Dockerfile and
  can be overridden with `NEO4J_server_memory_heap_max__size`,
  `NEO4J_server_memory_heap_initial__size` and
  `NEO4J_server_memory_pagecache_size`.

`gene_intel` service:

- Build and deploy settings: the table under "Deploying on Railway" in the
  root `README.md`.
- `NEO4J_URI`: `bolt://${{neo4j.RAILWAY_PRIVATE_DOMAIN}}:7687` (use `bolt://`,
  not `neo4j://`, for a single server)
- `NEO4J_USER`: `neo4j`
- `NEO4J_PASSWORD`: `${{neo4j.GRAPH_DB_PASSWORD}}`

## Running it locally

```bash
docker build --build-arg GENE_INTEL_SHA="$(git rev-parse HEAD)" -t gene-intel-graph graphdb
docker run --rm -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/choose-a-password gene-intel-graph
```
