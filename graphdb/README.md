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

Size of the full graph: 15.8 million nodes and 17.3 million relationships
(461,444 genes, 983,290 transcripts, 14.3 million exon/CDS/UTR/codon
features, 1.5 million CO_LOCATED_WITH edges). Cow and King cobra are in the
registry but have no GTF file, so they are skipped, as the loader does.

Domain annotations (UniProt and InterPro) are not part of this build. They come
from network APIs and stay a separate step.

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
first, then rerun it after changing the GTF files, the ingestion code or
`app/db/schema.py`. Pushes alone do not rebuild the graph.

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
