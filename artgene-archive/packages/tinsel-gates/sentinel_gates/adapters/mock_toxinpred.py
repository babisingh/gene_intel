"""Mock ToxinPred adapter — derives toxicity probability from sequence composition."""

from __future__ import annotations

from tinsel.models import GateStatus, ToxinPredResult

from sentinel_gates.adapters.base import BaseGateAdapter

# Residues over-represented in known toxins
_TOXIC_RESIDUES = frozenset("CKCRKR")
# Flag as toxic when >15 % of residues are in the toxic set
_TOXIC_FRACTION = 0.15
_FAIL_PROBABILITY = 0.5


class MockToxinPredAdapter(BaseGateAdapter):
    """Deterministic stand-in for a ToxinPred toxicity-prediction service.

    Toxicity probability is estimated from the fraction of cysteine, lysine,
    and arginine residues — crude but sufficient for integration tests.
    """

    gate_name = "toxinpred"

    def __init__(self, fail_probability: float = _FAIL_PROBABILITY) -> None:
        self._fail_probability = fail_probability

    async def run(self, sequence: str, sequence_id: str = "") -> ToxinPredResult:
        if not sequence:
            return ToxinPredResult(
                status=GateStatus.ERROR,
                error="Empty sequence received",
                details={"sequence_id": sequence_id},
            )

        upper = sequence.upper()
        toxic_count = sum(1 for aa in upper if aa in _TOXIC_RESIDUES)
        fraction = toxic_count / len(upper)

        # Scale fraction to a probability in [0, 1]
        probability = min(fraction / _TOXIC_FRACTION, 1.0)
        probability = round(probability, 4)

        is_toxic = probability >= self._fail_probability
        status = GateStatus.FAIL if is_toxic else GateStatus.PASS

        return ToxinPredResult(
            status=status,
            score=probability,
            toxicity_probability=probability,
            is_toxic=is_toxic,
            details={
                "sequence_id": sequence_id,
                "toxic_residue_fraction": round(fraction, 4),
            },
        )
