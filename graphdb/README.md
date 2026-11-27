# Graph database image

Neo4j Community 5.26 with the full 15-species Gene-Intel graph built into the
image. Railway runs it as the `neo4j` service in the `gene-intel` project, and
the web app reaches it over Railway's private network.

## Why the data is in the image

The app only reads the graph, and the graph is fully derived from the GTF files
in `backend/data/gtf`. Building it into the image means no volume (Railway
Hobby caps volumes at 5 GB, and this store is larger), nothing to back up, and
every build starts from a known state. A restart simply starts the same image
again.

## How the image is built

`graphdb/Dockerfile` has three stages:

1. `export_csv.py` runs the loader's own `ingest_species()` for every species
   in `SPECIES_REGISTRY`, with the Neo4j batch writers replaced by CSV
   writers. The result is the same graph that
   `python -m app.ingestion.run_ingest --all --step gtf` writes over Bolt.
2. `build_db.sh` bulk-imports the CSVs with `neo4j-admin database import`,
   starts a temporary local server to create the constraints and indexes from
   `app/db/schema.py`, checks every node and relationship count against the
   export's manifest, then stops the server and removes the build-time system
   database so the runtime container starts fresh.
3. The runtime stage copies the store to `/graph`.

Size of the full graph: 15.7 million nodes and 17.2 million relationships
(461,444 genes, 978,774 transcripts, 14.3 million exon/CDS/UTR/codon
features, 1.5 million CO_LOCATED_WITH edges). Cow and King cobra are in the
registry but have no GTF file, so they are skipped, as the loader does.

Domain annotations (UniProt and InterPro) are not part of this build. They come
from network APIs and stay a separate step.

## Railway settings

`neo4j` service:

- Source: this repo, config file `graphdb/railway.json` (Dockerfile path,
  watch paths, healthcheck). Only changes to the GTF files, the ingestion code,
  the schema or this folder rebuild it.
- `NEO4J_PASSWORD`: a generated secret.
- `NEO4J_AUTH`: `neo4j/${{NEO4J_PASSWORD}}`
- `PORT`: `7474`, used only by the healthcheck. No public domain.
- Memory defaults (heap 512m, page cache 768m) are set in the Dockerfile and
  can be overridden with `NEO4J_server_memory_heap_max__size`,
  `NEO4J_server_memory_heap_initial__size` and
  `NEO4J_server_memory_pagecache_size`.

`gene_intel` service:

- `NEO4J_URI`: `bolt://${{neo4j.RAILWAY_PRIVATE_DOMAIN}}:7687` (use `bolt://`,
  not `neo4j://`, for a single server)
- `NEO4J_USER`: `neo4j`
- `NEO4J_PASSWORD`: `${{neo4j.NEO4J_PASSWORD}}`

## Running it locally

```bash
docker build -f graphdb/Dockerfile -t gene-intel-graph .
docker run --rm -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/choose-a-password gene-intel-graph
```
