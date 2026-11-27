#!/bin/bash
# Uploads the graph build to the Railway `neo4j` service and starts a build.
#
# The service is deployed with `railway up`, not from GitHub: Railway applies
# the repo's root railway.json (the web app's config) to any service built
# from this repo, and new services cannot point at another config file. So
# this stages only what the graph build needs, with graphdb/Dockerfile as the
# root Dockerfile and no railway.json, and uploads that.
#
# The build takes several minutes: it parses every GTF file, imports the
# graph and builds the indexes. The running database keeps serving until the
# new one passes its healthcheck.
#
# Usage, from anywhere in a checkout, with the Railway CLI logged in:
#   graphdb/deploy.sh <railway project id> [environment] [service]
set -euo pipefail

PROJECT="${1:?usage: graphdb/deploy.sh <railway project id> [environment] [service]}"
ENVIRONMENT="${2:-production}"
SERVICE="${3:-neo4j}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$STAGE/backend/data" "$STAGE/graphdb"
cp -R "$ROOT/backend/app" "$STAGE/backend/app"
cp -R "$ROOT/backend/data/gtf" "$STAGE/backend/data/gtf"
cp "$ROOT/graphdb/export_csv.py" "$ROOT/graphdb/build_db.sh" "$STAGE/graphdb/"
cp "$ROOT/graphdb/Dockerfile" "$STAGE/Dockerfile"
find "$STAGE" -name __pycache__ -type d -prune -exec rm -rf {} +

echo "Uploading $(du -sh "$STAGE" | cut -f1) to service $SERVICE ($ENVIRONMENT)"
railway up "$STAGE" --path-as-root --detach -p "$PROJECT" -e "$ENVIRONMENT" -s "$SERVICE"
