#!/bin/bash
# Builds the Gene-Intel graph store at image build time (see graphdb/Dockerfile).
#
#   1. Bulk import of the CSV files written by export_csv.py.
#   2. A temporary server (local only, auth off) creates the app's
#      constraints and indexes from schema.cypher, waits for them to come
#      online, and checks every count against manifest.json.
#   3. The server stops and the build-time system database is removed, so the
#      runtime container starts as a fresh DBMS and sets the password from
#      NEO4J_AUTH. Indexes live in the neo4j database itself and are kept.
#
# Usage: build_db.sh <csv dir> <data dir>
set -Eeuo pipefail

CSV="${1:?usage: build_db.sh <csv dir> <data dir>}"
DATA="${2:?usage: build_db.sh <csv dir> <data dir>}"
CONF="${NEO4J_HOME:-/var/lib/neo4j}/conf/neo4j.conf"

as_neo4j() { su-exec neo4j:neo4j "$@"; }
manifest() { jq -r "$1" "$CSV/manifest.json"; }
# On failure, show the server's own logs in the build output.
trap 'tail -n 80 /logs/neo4j.log /logs/debug.log 2>/dev/null || true' ERR

mkdir -p "$DATA"
chown neo4j:neo4j "$DATA"

for key in server.directories.data dbms.security.auth_enabled server.default_listen_address \
           server.memory.heap.initial_size server.memory.heap.max_size server.memory.pagecache.size; do
  sed -i "/^${key//./\\.}=/d" "$CONF"
done
cat >> "$CONF" <<EOF

# graphdb/build_db.sh: build-time only, this stage is not shipped
server.directories.data=$DATA
dbms.security.auth_enabled=false
server.default_listen_address=127.0.0.1
server.memory.heap.initial_size=2g
server.memory.heap.max_size=2g
server.memory.pagecache.size=4g
EOF

echo "== import"
args=()
for pair in Species:species Gene:genes Transcript:transcripts Feature:features Domain:domains; do
  file="$CSV/${pair#*:}.csv"
  if [ -f "$file" ]; then args+=("--nodes=${pair%%:*}=$file"); fi
done
for pair in HAS_GENE:has_gene HAS_TRANSCRIPT:has_transcript HAS_FEATURE:has_feature \
            HAS_DOMAIN:has_domain CO_LOCATED_WITH:co_located_with; do
  file="$CSV/${pair#*:}.csv"
  if [ -f "$file" ]; then args+=("--relationships=${pair%%:*}=$file"); fi
done
as_neo4j neo4j-admin database import full neo4j "${args[@]}" \
  --threads="$(nproc)" --high-parallel-io=on --max-off-heap-memory=6g \
  --report-file=/tmp/import.report

echo "== schema"
as_neo4j neo4j start
cypher() { as_neo4j cypher-shell -a bolt://127.0.0.1:7687 -u neo4j -p build --non-interactive "$@"; }
for _ in $(seq 1 300); do
  if cypher "RETURN 1" >/dev/null 2>&1; then break; fi
  sleep 2
done
cypher "RETURN 1" >/dev/null
cypher -f "$CSV/schema.cypher"
cypher "CALL db.awaitIndexes(3600)"

echo "== check counts"
check() {
  local got
  got="$(cypher --format plain "$1" | tail -n 1)"
  if [ "$got" != "$2" ]; then
    echo "MISMATCH: $1 returned $got, expected $2" >&2
    exit 1
  fi
  echo "ok $2: $1"
}
for label in $(manifest '.nodes | keys[]'); do
  check "MATCH (n:\`$label\`) RETURN count(n)" "$(manifest ".nodes.$label")"
done
for type in $(manifest '.relationships | keys[]'); do
  check "MATCH ()-[r:\`$type\`]->() RETURN count(r)" "$(manifest ".relationships.$type")"
done
check "SHOW CONSTRAINTS YIELD name RETURN count(name)" "$(manifest '.constraints')"
check "SHOW INDEXES YIELD type WHERE type = 'RANGE' RETURN count(*)" \
      "$(( $(manifest '.constraints') + $(manifest '.indexes') ))"
check "SHOW INDEXES YIELD state WHERE state <> 'ONLINE' RETURN count(*)" "0"

echo "== stop"
as_neo4j neo4j stop

# Fresh DBMS at runtime: drop the build-time system database and auth state.
rm -rf "$DATA/databases/system" "$DATA/transactions/system" "$DATA/dbms" "$DATA/server_id"
du -sh "$DATA/databases/neo4j" "$DATA/transactions/neo4j"
