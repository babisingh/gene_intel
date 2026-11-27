"""
Tests for GET /api/gene/{gene_id} and its Agent C explanation.

The Neo4j query and Agent C are mocked, so these tests need no database and
make no Claude calls. A declined explanation used to fail the whole request
with a 500; the gene must still come back.
"""

import copy

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents.llm_reply import LLMRefusalError
from app.api import gene
from app.api.router import router as api_router
from app.dependencies import get_neo4j_driver

DETAIL = {
    "gene": {
        "gene_id": "ENSG00000139618",
        "name": "BRCA2",
        "species_taxon": "9606",
        "biotype": "protein_coding",
        "chromosome": "13",
        "start": 32315508,
        "end": 32400268,
        "strand": "+",
    },
    "domains": [],
    "species_name": "Homo sapiens",
    "transcripts": [],
    "features": [],
}


class FakeDriver:
    """Stands in for a neo4j Driver and its Session; get_gene_detail is mocked."""

    def session(self, **config):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def get_gene(monkeypatch, explain):
    monkeypatch.setattr(gene, "get_gene_detail", lambda session, gene_id: copy.deepcopy(DETAIL))
    monkeypatch.setattr(gene, "explain_single_gene", explain)
    app = FastAPI()
    app.include_router(api_router)
    app.dependency_overrides[get_neo4j_driver] = lambda: FakeDriver()
    return TestClient(app).get("/api/gene/ENSG00000139618")


def test_gene_detail_includes_the_explanation(monkeypatch):
    response = get_gene(monkeypatch, lambda gene_data, persona="student": "BRCA2 repairs DNA.")

    assert response.status_code == 200, response.json()
    assert response.json()["explanation"] == "BRCA2 repairs DNA."


def test_gene_detail_comes_back_when_claude_declines_to_explain_it(monkeypatch):
    def declined(gene_data, persona="student"):
        raise LLMRefusalError("Claude declined to answer (stop_reason=refusal)")

    response = get_gene(monkeypatch, declined)

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["gene"]["name"] == "BRCA2"
    assert body["explanation"] == gene.DECLINED_EXPLANATION
