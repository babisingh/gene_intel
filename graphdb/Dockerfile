# Gene-Intel graph database: Neo4j Community with the 15-species graph built in.
#
# Railway builds this as the `neo4j` service (settings in graphdb/railway.json).
# The graph is part of the image, not a volume: the app only reads it, and
# every build recreates it from backend/data/gtf with the loader's own code,
# so there is nothing to back up. See graphdb/README.md.
#
# The data directory is /graph, not /data: the base image declares
# VOLUME /data, and build-time contents of a declared volume are not
# reliably kept.

# 1. Export the graph as CSV with the app's ingestion code
FROM python:3.11-slim AS csv
WORKDIR /src
RUN pip install --no-cache-dir "pydantic-settings>=2.2.0" "neo4j>=5.19.0"
COPY backend/app ./backend/app
COPY backend/data/gtf ./backend/data/gtf
COPY graphdb/export_csv.py ./graphdb/
RUN python graphdb/export_csv.py --backend /src/backend --out /csv

# 2. Bulk import, create the app's indexes, check every count
FROM neo4j:5.26.32-community AS store
ENV NEO4J_SHUTDOWN_TIMEOUT=900 HEAP_SIZE=2g
COPY --from=csv /csv /csv
COPY graphdb/build_db.sh /build_db.sh
RUN bash /build_db.sh /csv /graph && rm -rf /csv

# 3. Runtime image. Memory settings are defaults; Railway variables override.
FROM neo4j:5.26.32-community
COPY --from=store --chown=neo4j:neo4j /graph /graph
ENV NEO4J_server_directories_data=/graph \
    NEO4J_server_default__listen__address=:: \
    NEO4J_server_memory_heap_initial__size=512m \
    NEO4J_server_memory_heap_max__size=512m \
    NEO4J_server_memory_pagecache_size=768m \
    NEO4J_db_tx__log_rotation_retention__policy="100M size"
