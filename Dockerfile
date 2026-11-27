# ── Gene-Intel web app: production Docker image ───────────────────────────────
#
# Railway builds this file for the gene_intel service (project gene-intel).
# The image holds the FastAPI backend and the built React frontend. The graph
# database is a separate Railway service, neo4j, built from graphdb/ with the
# graph already in its image (see graphdb/README.md). The app reaches it over
# Railway's private network:
#
#   gene_intel (this image) --bolt, private network--> neo4j (graphdb/Dockerfile)
#
# backend/ is copied in whole, so the GTF files in backend/data/gtf are in this
# image too (.dockerignore only leaves out the top-level data/ folder). The web
# app does not read them at runtime: graphdb/ builds the graph from them into
# the neo4j image.
#
# Variables the app needs, set on the gene_intel service in Railway
# (graphdb/README.md, "Railway settings", shows what the NEO4J_* ones reference):
#   NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD   the neo4j service, over bolt://
#   ANTHROPIC_API_KEY                        the Anthropic API key
#
# Pushes to main that change this file, requirements.txt, backend/, frontend/
# or scripts/ deploy gene_intel to production (README, "Deploying on Railway").
#
# ── Stage 1: Build React frontend ─────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
# npm ci installs exactly what package-lock.json lists, and fails if the
# lockfile does not match package.json.
RUN npm ci
COPY frontend/ ./
# VITE_API_BASE_URL is intentionally empty so the frontend uses relative URLs
# (same origin as the backend in production).
RUN npm run build

# ── Stage 2: Python backend ────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime
WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./backend/
COPY scripts/ ./scripts/

# Copy built frontend assets from stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Python must find the `app` package inside backend/
ENV PYTHONPATH=/app/backend
ENV APP_ENV=production

# Railway dynamically assigns $PORT; default to 8000 for local Docker runs
EXPOSE 8000
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
