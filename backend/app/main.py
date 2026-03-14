"""
FastAPI application factory + lifespan.

Startup:  initialise Neo4j schema, verify connectivity
Shutdown: close Neo4j driver
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.db.neo4j_client import get_driver, close_driver, verify_connectivity
from app.db.schema import init_schema
from app.api.router import router as api_router
from app.models.api_models import HealthResponse

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info("Gene-Intel starting up…")
    driver = get_driver()
    if verify_connectivity():
        logger.info("Neo4j connected — initialising schema")
        init_schema(driver)
    else:
        logger.warning("Neo4j not reachable at startup — some endpoints will fail")
    yield
    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("Gene-Intel shutting down…")
    close_driver()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Gene-Intel Discovery Engine",
        version="2.0.0",
        description=(
            "Semantic genomic graph search across 15 species. "
            "Ask questions in plain English — get interactive gene networks back."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.get("/api/health", response_model=HealthResponse, tags=["health"])
    def health():
        neo4j_ok = verify_connectivity()
        # Count loaded species as a proxy for LLM readiness check (avoids API call cost)
        species_count = 0
        try:
            driver = get_driver()
            with driver.session() as session:
                result = session.run("MATCH (s:Species) RETURN count(s) AS n")
                record = result.single()
                species_count = record["n"] if record else 0
        except Exception:
            pass

        return HealthResponse(
            neo4j="ok" if neo4j_ok else "error",
            llm="ok" if settings.anthropic_api_key else "error",
            species_loaded=species_count,
        )

    # ── Serve built React frontend (production / Railway) ─────────────────────
    # Registered last so all /api/* routes take priority over the SPA catch-all.
    # The Dockerfile copies the Vite build output to /app/frontend/dist.
    # In development (no dist folder) the Vite dev server handles the UI.
    _frontend_dist = Path(__file__).parent.parent.parent.parent / "frontend" / "dist"
    if _frontend_dist.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=str(_frontend_dist / "assets")),
            name="frontend-assets",
        )

        # SPA catch-all: return index.html for any path so React Router works
        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str):  # noqa: ARG001
            return FileResponse(str(_frontend_dist / "index.html"))

    return app


app = create_app()
