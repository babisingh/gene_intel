"""Mock NCBI BLAST adapter — returns canned homology hits for testing."""

from __future__ import annotations

from tinsel.models import BlastResult, GateStatus

from sentinel_gates.adapters.base import BaseGateAdapter

# If a sequence matches this prefix we simulate a high-identity dangerous hit
_DANGER_PREFIX = "MKTLL"
_DANGER_HIT = {
    "accession": "AAB99999",
    "description": "toxin-like protein [synthetic construct]",
    "identity": 99.5,
    "e_value": 1e-120,
    "bit_score": 450.0,
}
_SAFE_HIT = {
    "accession": "NP_000000",
    "description": "hypothetical protein",
    "identity": 32.1,
    "e_value": 0.42,
    "bit_score": 38.2,
}

# Identity threshold above which the gate FAILs (flags dangerous homology)
_FAIL_IDENTITY = 90.0


class MockNCBIBlastAdapter(BaseGateAdapter):
    """Deterministic stand-in for an NCBI BLAST API call.

    Sequences starting with ``MKTLL`` receive a high-identity dangerous hit;
    all others get a low-identity benign result.
    """

    gate_name = "ncbi_blast"

    def __init__(self, fail_identity: float = _FAIL_IDENTITY) -> None:
        self._fail_identity = fail_identity

    async def run(self, sequence: str, sequence_id: str = "") -> BlastResult:
        seq_upper = sequence.upper()

        if seq_upper.startswith(_DANGER_PREFIX.upper()):
            top_hits = [_DANGER_HIT]
            max_identity = _DANGER_HIT["identity"]
            e_value_min = _DANGER_HIT["e_value"]
        else:
            top_hits = [_SAFE_HIT]
            max_identity = _SAFE_HIT["identity"]
            e_value_min = _SAFE_HIT["e_value"]

        status = GateStatus.FAIL if max_identity >= self._fail_identity else GateStatus.PASS

        return BlastResult(
            status=status,
            score=max_identity,
            top_hits=top_hits,
            max_identity=max_identity,
            e_value_min=e_value_min,
            details={"sequence_id": sequence_id, "db": "mock_nr"},
        )
