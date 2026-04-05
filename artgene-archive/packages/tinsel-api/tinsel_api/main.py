"""FastAPI application with Mangum adapter for AWS Lambda / API Gateway."""

from __future__ import annotations

from fastapi import FastAPI
from mangum import Mangum
from pydantic import BaseModel

from tinsel.models import GateStatus, PipelineResult
from sentinel_gates.adapters import (
    MockESMFoldAdapter,
    MockNCBIBlastAdapter,
    MockToxinPredAdapter,
)
from sentinel_gates.pipeline import GatePipeline

app = FastAPI(
    title="Tinsel API",
    version="0.1.0",
    description="Biosecurity sequence screening pipeline",
)

# Default pipeline wired with mock adapters (swap for real adapters in production)
_pipeline = GatePipeline([
    MockESMFoldAdapter(),
    MockNCBIBlastAdapter(),
    MockToxinPredAdapter(),
])


class ScreenRequest(BaseModel):
    sequence_id: str
    sequence: str


class ScreenResponse(BaseModel):
    result: PipelineResult
    flagged: bool


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/screen", response_model=ScreenResponse)
async def screen(req: ScreenRequest) -> ScreenResponse:
    result = await _pipeline.run(sequence=req.sequence, sequence_id=req.sequence_id)
    flagged = result.overall_status in (GateStatus.FAIL, GateStatus.ERROR)
    return ScreenResponse(result=result, flagged=flagged)


# AWS Lambda entrypoint
handler = Mangum(app, lifespan="off")
