#!/bin/bash
# Starts a build of the Railway `neo4j` service from the current commit.
#
# The service is deployed with `railway up`, not from GitHub: its Dockerfile
# path setting is `Dockerfile`, so built from GitHub it would build the
# repo's root Dockerfile, which is the web app. The upload is only
# graphdb/Dockerfile with GENE_INTEL_SHA filled in; the build fetches the code
# and GTF files from GitHub at that commit, so the commit must be pushed
# first.
#
# The build takes a while: it parses every GTF file, imports the graph and
# builds the indexes. The running database keeps serving until the new one
# passes its healthcheck.
#
# Usage, from anywhere in a checkout, with the Railway CLI logged in:
#   graphdb/deploy.sh <railway project id> [environment] [service]
set -euo pipefail

PROJECT="${1:?usage: graphdb/deploy.sh <railway project id> [environment] [service]}"
ENVIRONMENT="${2:-production}"
SERVICE="${3:-neo4j}"
cd "$(dirname "$0")/.."

SHA="$(git rev-parse HEAD)"
if [ -z "$(git branch -r --contains "$SHA")" ]; then
  echo "Commit $SHA is not on any remote branch. Push it first." >&2
  exit 1
fi
if [ -n "$(git status --porcelain -- graphdb backend)" ]; then
  echo "Note: uncommitted changes under graphdb/ or backend/ are not part of the build." >&2
fi

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
sed "s/^ARG GENE_INTEL_SHA$/ARG GENE_INTEL_SHA=$SHA/" graphdb/Dockerfile > "$STAGE/Dockerfile"
grep -q "^ARG GENE_INTEL_SHA=$SHA$" "$STAGE/Dockerfile"

echo "Building $SERVICE ($ENVIRONMENT) from commit $SHA"
railway up "$STAGE" --path-as-root --detach -p "$PROJECT" -e "$ENVIRONMENT" -s "$SERVICE"
