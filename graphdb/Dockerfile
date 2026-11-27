# Gene-Intel graph database: Neo4j Community with the 15-species graph built in.
#
# Railway builds this as the `neo4j` service, uploaded by graphdb/deploy.sh.
# The graph is part of the image, not a volume: the app only reads it, and
# every build recreates it from backend/data/gtf with the loader's own code,
# so there is nothing to back up. See graphdb/README.md.
#
# The build needs no context. The ingestion code, GTF files and build scripts
# are fetched from GitHub at GENE_INTEL_SHA, a pushed commit; deploy.sh fills
# it in. (Railway's upload limit is smaller than the GTF files.)
#
# The data directory is /graph, not /data: the base image declares
# VOLUME /data, and build-time contents of a declared volume are not
# reliably kept.
ARG GENE_INTEL_REPO=babisingh/gene_intel
ARG GENE_INTEL_SHA

# 1. Fetch the sources and export the graph as CSV with the app's ingestion code
FROM python:3.11-slim AS csv
ARG GENE_INTEL_REPO
ARG GENE_INTEL_SHA
RUN test -n "$GENE_INTEL_SHA" || { echo "GENE_INTEL_SHA build arg is required" >&2; exit 1; }
ADD https://codeload.github.com/${GENE_INTEL_REPO}/tar.gz/${GENE_INTEL_SHA} /tmp/src.tar.gz
RUN mkdir /src && tar -xzf /tmp/src.tar.gz -C /src --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir "pydantic-settings>=2.2.0" "neo4j>=5.19.0"
RUN python /src/graphdb/export_csv.py --backend /src/backend --out /csv

# 2. Bulk import, create the app's indexes, check every count
FROM neo4j:5.26.32-community AS store
ENV NEO4J_SHUTDOWN_TIMEOUT=900 HEAP_SIZE=2g
COPY --from=csv /csv /csv
COPY --from=csv /src/graphdb/build_db.sh /build_db.sh
RUN bash /build_db.sh /csv /graph && rm -rf /csv

# 3. Runtime image. Memory settings are defaults; Railway variables override.
FROM neo4j:5.26.32-community
ARG GENE_INTEL_SHA
LABEL org.opencontainers.image.revision=$GENE_INTEL_SHA
COPY --from=store --chown=neo4j:neo4j /graph /graph
# Variables named NEO4J_* become Neo4j settings (see the image's entrypoint),
# so the password variable on Railway must use another prefix.
ENV NEO4J_server_directories_data=/graph \
    NEO4J_server_default__listen__address=:: \
    NEO4J_server_memory_heap_initial__size=512m \
    NEO4J_server_memory_heap_max__size=512m \
    NEO4J_server_memory_pagecache_size=768m \
    NEO4J_db_tx__log_rotation_retention__policy="100M size" \
    NEO4J_dbms_usage__report_enabled=false \
    TINI_SUBREAPER=true
