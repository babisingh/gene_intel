"""Mock ESMFold adapter — returns deterministic pLDDT scores for testing."""

from __future__ import annotations

import hashlib

from tinsel.models import ESMFoldResult, GateStatus

from sentinel_gates.adapters.base import BaseGateAdapter

# Confidence thresholds (mirror real ESMFold interpretation)
_HIGH_PLDDT = 70.0
_MEDIUM_PLDDT = 50.0


class MockESMFoldAdapter(BaseGateAdapter):
    """Deterministic stand-in for the ESMFold structure-prediction service.

    The mock derives a pLDDT score from the MD5 hash of the sequence so that
    repeated calls with the same input always return the same result, while
    different sequences get different scores — useful for property-based tests.
    """

    gate_name = "esmfold"

    def __init__(self, fail_threshold: float = _MEDIUM_PLDDT) -> None:
        self._fail_threshold = fail_threshold

    async def run(self, sequence: str, sequence_id: str = "") -> ESMFoldResult:
        digest = hashlib.md5(sequence.encode()).digest()
        # Map first two bytes to 0–100 range
        raw = int.from_bytes(digest[:2], "big")
        plddt_mean = round((raw / 65535) * 100, 2)
        plddt_min = round(plddt_mean * 0.85, 2)

        if plddt_mean >= _HIGH_PLDDT:
            confidence = "high"
        elif plddt_mean >= _MEDIUM_PLDDT:
            confidence = "medium"
        else:
            confidence = "low"

        status = GateStatus.PASS if plddt_mean >= self._fail_threshold else GateStatus.FAIL

        return ESMFoldResult(
            status=status,
            score=plddt_mean,
            plddt_mean=plddt_mean,
            plddt_min=plddt_min,
            structure_confidence=confidence,
            details={"sequence_id": sequence_id, "sequence_length": len(sequence)},
        )
