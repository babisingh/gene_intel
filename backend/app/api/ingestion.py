"""
POST /api/ingest/status — Job polling endpoint (read-only in MVP).
Actual ingestion runs via CLI: python -m app.ingestion.run_ingest
"""

from fastapi import APIRouter
from app.models.api_models import IngestStatusResponse

router = APIRouter()

# In MVP, ingestion is CLI-only. This endpoint provides a stub for polling UI.
_ingest_status = {
    "status": "idle",
    "species": None,
    "progress": None,
    "error": None,
}


@router.get("/ingest/status", response_model=IngestStatusResponse)
def get_ingest_status():
    """Return current ingestion job status."""
    return IngestStatusResponse(**_ingest_status)
