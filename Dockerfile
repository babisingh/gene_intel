# ── Gene-Intel — Production Docker image ──────────────────────────────────────
#
# Architecture:
#   ┌─────────────┐     ┌──────────────────┐     ┌───────────────────┐
#   │  Local PC   │────▶│  Neo4j Aura      │◀────│  Railway (this    │
#   │  (ingest)   │     │  (graph DB cloud)│     │   Dockerfile)     │
#   └─────────────┘     └──────────────────┘     └───────────────────┘
#
# This image contains ONLY the web application (FastAPI + React).
# GTF and BioMart data files are EXCLUDED via .dockerignore — they live on
# the local machine used for ingestion, not in Railway.
#
# Required Railway environment variables:
#   NEO4J_URI         neo4j+s://<id>.databases.neo4j.io
#   NEO4J_USER        neo4j
#   NEO4J_PASSWORD    <password>
#   ANTHROPIC_API_KEY sk-ant-api03-…
#
# ── Stage 1: Build React frontend ─────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
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
