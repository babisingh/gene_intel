"""
Mounts all sub-routers under /api.
"""

from fastapi import APIRouter
from app.api import search, species, gene, neighborhood, ingestion, evolution

router = APIRouter(prefix="/api")

router.include_router(search.router)
router.include_router(species.router)
router.include_router(gene.router)
router.include_router(neighborhood.router)
router.include_router(ingestion.router)
router.include_router(evolution.router)
