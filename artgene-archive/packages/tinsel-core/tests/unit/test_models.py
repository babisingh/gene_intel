"""Unit tests for tinsel.models — 25 tests."""

import pytest
from pydantic import ValidationError

from tinsel.models import (
    BlastResult,
    ESMFoldResult,
    GateResult,
    GateStatus,
    PipelineResult,
    ToxinPredResult,
)


# ---------------------------------------------------------------------------
# GateStatus enum
# ---------------------------------------------------------------------------

def test_gate_status_values():
    assert GateStatus.PASS == "pass"
    assert GateStatus.FAIL == "fail"
    assert GateStatus.ERROR == "error"
    assert GateStatus.PENDING == "pending"


def test_gate_status_is_str_enum():
    assert isinstance(GateStatus.PASS, str)


# ---------------------------------------------------------------------------
# GateResult
# ---------------------------------------------------------------------------

def test_gate_result_minimal():
    r = GateResult(gate_name="test_gate")
    assert r.gate_name == "test_gate"
    assert r.status == GateStatus.PENDING
    assert r.score is None
    assert r.details == {}
    assert r.error is None


def test_gate_result_full():
    r = GateResult(
        gate_name="my_gate",
        status=GateStatus.PASS,
        score=0.95,
        details={"key": "value"},
        error=None,
    )
    assert r.status == GateStatus.PASS
    assert r.score == pytest.approx(0.95)
    assert r.details["key"] == "value"


def test_gate_result_fail_status():
    r = GateResult(gate_name="g", status=GateStatus.FAIL)
    assert r.status == GateStatus.FAIL


def test_gate_result_error_status():
    r = GateResult(gate_name="g", status=GateStatus.ERROR, error="timeout")
    assert r.status == GateStatus.ERROR
    assert r.error == "timeout"


def test_gate_result_details_default_is_empty_dict():
    r = GateResult(gate_name="g")
    assert r.details == {}


def test_gate_result_details_not_shared_between_instances():
    a = GateResult(gate_name="a")
    b = GateResult(gate_name="b")
    a.details["x"] = 1
    assert "x" not in b.details


def test_gate_result_json_roundtrip():
    r = GateResult(gate_name="g", status=GateStatus.PASS, score=0.5, details={"n": 1})
    r2 = GateResult.model_validate_json(r.model_dump_json())
    assert r2 == r


def test_gate_result_requires_gate_name():
    with pytest.raises(ValidationError):
        GateResult()  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# ESMFoldResult
# ---------------------------------------------------------------------------

def test_esmfold_result_default_gate_name():
    r = ESMFoldResult(status=GateStatus.PENDING)
    assert r.gate_name == "esmfold"


def test_esmfold_result_plddt_fields():
    r = ESMFoldResult(plddt_mean=85.3, plddt_min=62.1, status=GateStatus.PASS)
    assert r.plddt_mean == pytest.approx(85.3)
    assert r.plddt_min == pytest.approx(62.1)


def test_esmfold_result_structure_confidence():
    r = ESMFoldResult(structure_confidence="high", status=GateStatus.PASS)
    assert r.structure_confidence == "high"


def test_esmfold_result_optional_fields_default_none():
    r = ESMFoldResult()
    assert r.plddt_mean is None
    assert r.plddt_min is None
    assert r.structure_confidence is None


def test_esmfold_result_inherits_gate_result():
    r = ESMFoldResult(status=GateStatus.PASS)
    assert isinstance(r, GateResult)


# ---------------------------------------------------------------------------
# BlastResult
# ---------------------------------------------------------------------------

def test_blast_result_default_gate_name():
    r = BlastResult(status=GateStatus.PENDING)
    assert r.gate_name == "ncbi_blast"


def test_blast_result_top_hits_default_empty():
    r = BlastResult()
    assert r.top_hits == []


def test_blast_result_with_hits():
    hits = [{"accession": "AAB12345", "identity": 99.5, "e_value": 1e-80}]
    r = BlastResult(top_hits=hits, max_identity=99.5, e_value_min=1e-80, status=GateStatus.FAIL)
    assert len(r.top_hits) == 1
    assert r.max_identity == pytest.approx(99.5)
    assert r.e_value_min == pytest.approx(1e-80)


def test_blast_result_inherits_gate_result():
    r = BlastResult()
    assert isinstance(r, GateResult)


# ---------------------------------------------------------------------------
# ToxinPredResult
# ---------------------------------------------------------------------------

def test_toxinpred_result_default_gate_name():
    r = ToxinPredResult()
    assert r.gate_name == "toxinpred"


def test_toxinpred_result_toxic():
    r = ToxinPredResult(toxicity_probability=0.91, is_toxic=True, status=GateStatus.FAIL)
    assert r.is_toxic is True
    assert r.toxicity_probability == pytest.approx(0.91)


def test_toxinpred_result_not_toxic():
    r = ToxinPredResult(toxicity_probability=0.07, is_toxic=False, status=GateStatus.PASS)
    assert r.is_toxic is False


def test_toxinpred_result_inherits_gate_result():
    assert isinstance(ToxinPredResult(), GateResult)


# ---------------------------------------------------------------------------
# PipelineResult
# ---------------------------------------------------------------------------

def test_pipeline_result_minimal():
    pr = PipelineResult(sequence_id="seq001", sequence="ACGT")
    assert pr.sequence_id == "seq001"
    assert pr.overall_status == GateStatus.PENDING
    assert pr.gates == []
    assert pr.metadata == {}


def test_pipeline_result_with_gates():
    g1 = ESMFoldResult(status=GateStatus.PASS)
    g2 = ToxinPredResult(status=GateStatus.FAIL)
    pr = PipelineResult(
        sequence_id="s1",
        sequence="MKTLL",
        gates=[g1, g2],
        overall_status=GateStatus.FAIL,
    )
    assert len(pr.gates) == 2
    assert pr.overall_status == GateStatus.FAIL


def test_pipeline_result_requires_sequence_id():
    with pytest.raises(ValidationError):
        PipelineResult(sequence="ACGT")  # type: ignore[call-arg]


def test_pipeline_result_requires_sequence():
    with pytest.raises(ValidationError):
        PipelineResult(sequence_id="s1")  # type: ignore[call-arg]
