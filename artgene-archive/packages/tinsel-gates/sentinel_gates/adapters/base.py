"""Abstract base class that all gate adapters must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod

from tinsel.models import GateResult


class BaseGateAdapter(ABC):
    """ABC for a single biosecurity gate.

    Each concrete adapter wraps one external tool (ESMFold, BLAST, ToxinPred,
    …) and exposes a uniform async interface so the :class:`GatePipeline`
    can orchestrate them without knowing their internals.
    """

    #: Stable identifier used in :attr:`~tinsel.models.GateResult.gate_name`.
    gate_name: str

    @abstractmethod
    async def run(self, sequence: str, sequence_id: str = "") -> GateResult:
        """Run the gate against *sequence* and return a :class:`GateResult`.

        Parameters
        ----------
        sequence:
            Raw amino-acid or nucleotide string to evaluate.
        sequence_id:
            Optional label for logging / tracing.

        Returns
        -------
        GateResult
            Populated result including status, score and any extra fields
            defined by the concrete subclass.
        """

    @property
    def name(self) -> str:
        """Convenience alias so callers can use ``adapter.name``."""
        return self.gate_name

    def __repr__(self) -> str:  # pragma: no cover
        return f"{self.__class__.__name__}(gate_name={self.gate_name!r})"
