"""Async gate orchestrator — runs all adapters concurrently and aggregates results."""

from __future__ import annotations

import asyncio
from typing import List, Sequence

from tinsel.models import GateResult, GateStatus, PipelineResult

from sentinel_gates.adapters.base import BaseGateAdapter


class GatePipeline:
    """Run a list of :class:`BaseGateAdapter` instances concurrently.

    The pipeline is intentionally simple: it gathers all gate coroutines in
    parallel and rolls up the overall status using fail-fast semantics — if
    *any* gate returns FAIL or ERROR the pipeline result is marked accordingly.

    Example usage::

        pipeline = GatePipeline([
            MockESMFoldAdapter(),
            MockNCBIBlastAdapter(),
            MockToxinPredAdapter(),
        ])
        result = await pipeline.run(sequence="MKTLLLTLVVV", sequence_id="seq_001")
    """

    def __init__(self, adapters: Sequence[BaseGateAdapter]) -> None:
        self._adapters = list(adapters)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, sequence: str, sequence_id: str = "") -> PipelineResult:
        """Evaluate *sequence* through all gates and return a :class:`PipelineResult`."""
        gate_results: List[GateResult] = await asyncio.gather(
            *[adapter.run(sequence, sequence_id) for adapter in self._adapters],
            return_exceptions=False,
        )

        overall = self._aggregate_status(gate_results)

        return PipelineResult(
            sequence_id=sequence_id,
            sequence=sequence,
            gates=gate_results,
            overall_status=overall,
            metadata={"gate_count": len(gate_results)},
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _aggregate_status(results: List[GateResult]) -> GateStatus:
        """Return the most severe status across all gate results."""
        statuses = {r.status for r in results}
        if GateStatus.ERROR in statuses:
            return GateStatus.ERROR
        if GateStatus.FAIL in statuses:
            return GateStatus.FAIL
        if GateStatus.PENDING in statuses:
            return GateStatus.PENDING
        return GateStatus.PASS
