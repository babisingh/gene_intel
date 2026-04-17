"""Gate result schemas for the Tinsel biosecurity screening pipeline."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GateStatus(str, Enum):
    """Status of a single gate evaluation."""

    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    PENDING = "pending"


class GateResult(BaseModel):
    """Base schema for all gate adapter results."""

    gate_name: str
    status: GateStatus = GateStatus.PENDING
    score: Optional[float] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None

    model_config = {"use_enum_values": False}


class ESMFoldResult(GateResult):
    """Result from the ESMFold structure-prediction gate."""

    gate_name: str = "esmfold"
    plddt_mean: Optional[float] = None
    plddt_min: Optional[float] = None
    structure_confidence: Optional[str] = None  # "high" | "medium" | "low"


class BlastResult(GateResult):
    """Result from the NCBI BLAST homology gate."""

    gate_name: str = "ncbi_blast"
    top_hits: List[Dict[str, Any]] = Field(default_factory=list)
    max_identity: Optional[float] = None
    e_value_min: Optional[float] = None


class ToxinPredResult(GateResult):
    """Result from the ToxinPred toxicity-prediction gate."""

    gate_name: str = "toxinpred"
    toxicity_probability: Optional[float] = None
    is_toxic: Optional[bool] = None


class PipelineResult(BaseModel):
    """Aggregate result for a full gate pipeline run on one sequence."""

    sequence_id: str
    sequence: str
    gates: List[GateResult] = Field(default_factory=list)
    overall_status: GateStatus = GateStatus.PENDING
    metadata: Dict[str, Any] = Field(default_factory=dict)
