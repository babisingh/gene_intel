"""
Tests for the search pipeline: app/agents/graph_workflow.py and POST /api/search.

The Neo4j driver and both agents are mocked, so these tests need no database
and make no Claude calls.

Regression covered: on 2026-11-27 Neo4j rejected a generated query with
Neo.ClientError.Statement.SyntaxError, and the API still answered 200 with
result_count 0, because Agent C ran after the failure and reset success and
error. A failed step must end the run, and the client must get an error.

Also covered: at 19:41 UTC the same day Claude declined a question, and the
API answered 500 "Empty response from LLM (stop_reason=refusal)". A declined
question must end the run at Agent A with a 422 and a message people can act on.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from app.agents import graph_workflow
from app.agents.llm_reply import LLMRefusalError
from app.api.router import router as api_router
from app.db.queries import search_queries
from app.dependencies import get_neo4j_driver

QUERY = "human genes with the longest coding sequence"
CYPHER = (
    "MATCH (g:Gene) WHERE g.species_taxon = '9606' "
    "RETURN g AS gene, [] AS domains, g.species_taxon AS species "
    "ORDER BY gene.cds_length DESC LIMIT 10"
)
# The shape that failed on 2026-11-27: the query inside a markdown code fence,
# which the validator let through and Neo4j rejected at line 1, column 1.
FENCED_CYPHER = f"```cypher\n{CYPHER}\n```"
EXPLANATION = "## Summary\nOne human gene matched."
BRCA2_RECORD = {
    "gene": {
        "gene_id": "ENSG00000139618",
        "name": "BRCA2",
        "species_taxon": "9606",
        "biotype": "protein_coding",
        "chromosome": "13",
    },
    "domains": [],
    "species": "9606",
}


def syntax_error() -> Neo4jError:
    """The exception the driver raises when Neo4j rejects a query's syntax.

    Built with the driver's own hydration, as it does for a server failure
    message, so str() has the same shape as in production. The message text
    is abbreviated.
    """
    return Neo4jError._hydrate_neo4j(
        code="Neo.ClientError.Statement.SyntaxError",
        message="Invalid input '```' (line 1, column 1 (offset: 0))",
    )


class FakeSession:
    """Stands in for a neo4j Session: returns canned records, or raises."""

    def __init__(self, records=(), error=None):
        self.records = list(records)
        self.error = error
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def run(self, query, **params):
        self.queries.append(query)
        if self.error is not None:
            raise self.error
        return list(self.records)


class FakeDriver:
    """Stands in for a neo4j Driver; counts the sessions it hands out."""

    def __init__(self, records=(), error=None):
        self.fake_session = FakeSession(records, error)
        self.sessions_opened = 0

    def session(self, **config):
        self.sessions_opened += 1
        return self.fake_session


@pytest.fixture
def agent_a(monkeypatch):
    """Agent A, mocked: returns CYPHER as a validated query unless a test says otherwise."""
    mock = MagicMock(return_value={"cypher": CYPHER, "success": True, "error": None})
    monkeypatch.setattr(graph_workflow, "generate_cypher_with_retry", mock)
    return mock


@pytest.fixture
def agent_c(monkeypatch):
    """Agent C, mocked: returns EXPLANATION."""
    mock = MagicMock(return_value=EXPLANATION)
    monkeypatch.setattr(graph_workflow, "explain_results", mock)
    return mock


@pytest.fixture(autouse=True)
def species_names(monkeypatch):
    """Seed the species-name cache, so FakeSession only sees the search query."""
    monkeypatch.setattr(search_queries, "_species_name_cache", {"9606": "Homo sapiens"})


async def run_workflow(driver):
    return await graph_workflow.run_search(
        nl_query=QUERY,
        persona="researcher",
        species_filter=None,
        limit=10,
        driver=driver,
    )


def post_search(driver):
    app = FastAPI()
    app.include_router(api_router)
    app.dependency_overrides[get_neo4j_driver] = lambda: driver
    return TestClient(app).post("/api/search", json={"query": QUERY, "persona": "researcher"})


# ── Workflow ──────────────────────────────────────────────────────────────────


async def test_neo4j_failure_ends_the_run_before_agent_c(agent_a, agent_c):
    agent_a.return_value = {"cypher": FENCED_CYPHER, "success": True, "error": None}

    state = await run_workflow(FakeDriver(error=syntax_error()))

    assert state["success"] is False
    assert state["failed_step"] == "neo4j"
    assert state["error"].startswith("Query execution error: ")
    assert "Neo.ClientError.Statement.SyntaxError" in state["error"]
    assert state["raw_results"] == []
    agent_c.assert_not_called()


async def test_cypher_generation_failure_skips_neo4j_and_agent_c(agent_a, agent_c):
    agent_a.return_value = {
        "cypher": "MATCH (g:Gene) RETURN g AS gene",
        "success": False,
        "error": "Query must contain a LIMIT clause (max 300)",
    }
    driver = FakeDriver()

    state = await run_workflow(driver)

    assert state["success"] is False
    assert state["failed_step"] == "agent_a"
    assert state["error"] == "Cypher generation failed: Query must contain a LIMIT clause (max 300)"
    assert driver.sessions_opened == 0
    agent_c.assert_not_called()


async def test_a_declined_question_ends_the_run_with_a_clear_message(agent_a, agent_c):
    agent_a.side_effect = LLMRefusalError("Claude declined to answer (stop_reason=refusal)")
    driver = FakeDriver()

    state = await run_workflow(driver)

    assert state["success"] is False
    assert state["failed_step"] == "agent_a"
    assert state["error"] == graph_workflow.DECLINED_MESSAGE
    assert driver.sessions_opened == 0
    agent_c.assert_not_called()


async def test_successful_search_runs_agent_c_on_the_results(agent_a, agent_c):
    driver = FakeDriver(records=[BRCA2_RECORD])

    state = await run_workflow(driver)

    assert state["success"] is True
    assert state["error"] is None
    assert state["failed_step"] is None
    assert driver.fake_session.queries == [CYPHER]
    assert [gene["name"] for gene in state["raw_results"]] == ["BRCA2"]
    assert state["explanation"] == EXPLANATION
    agent_c.assert_called_once()
    assert agent_c.call_args.kwargs["results"] == state["raw_results"]


async def test_agent_c_failure_still_returns_the_results(agent_a, agent_c):
    agent_c.side_effect = RuntimeError("Claude API unavailable")

    state = await run_workflow(FakeDriver(records=[BRCA2_RECORD]))

    assert state["success"] is True
    assert state["error"] is None
    assert state["explanation"] == "Results retrieved. Explanation unavailable."
    assert [gene["name"] for gene in state["raw_results"]] == ["BRCA2"]


# ── POST /api/search ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "error, expected_in_detail",
    [
        (syntax_error(), "Neo.ClientError.Statement.SyntaxError"),
        (ServiceUnavailable("Couldn't connect to neo4j:7687"), "Couldn't connect to neo4j:7687"),
    ],
    ids=["query rejected", "database unreachable"],
)
def test_search_reports_a_failed_neo4j_step_as_502(agent_a, agent_c, error, expected_in_detail):
    agent_a.return_value = {"cypher": FENCED_CYPHER, "success": True, "error": None}

    response = post_search(FakeDriver(error=error))

    assert response.status_code == 502, response.json()
    detail = response.json()["detail"]
    assert detail.startswith("Query execution error: ")
    assert expected_in_detail in detail
    agent_c.assert_not_called()


def test_search_reports_cypher_generation_failure_as_422(agent_a, agent_c):
    agent_a.return_value = {
        "cypher": "MATCH (g:Gene) RETURN g AS gene",
        "success": False,
        "error": "Query must contain a LIMIT clause (max 300)",
    }
    driver = FakeDriver()

    response = post_search(driver)

    assert response.status_code == 422, response.json()
    assert response.json() == {
        "detail": "Cypher generation failed: Query must contain a LIMIT clause (max 300)"
    }
    assert driver.sessions_opened == 0
    agent_c.assert_not_called()


def test_search_reports_a_declined_question_as_422_with_a_clear_message(agent_a, agent_c):
    agent_a.side_effect = LLMRefusalError("Claude declined to answer (stop_reason=refusal)")
    driver = FakeDriver()

    response = post_search(driver)

    assert response.status_code == 422, response.json()
    assert response.json() == {"detail": graph_workflow.DECLINED_MESSAGE}
    assert driver.sessions_opened == 0
    agent_c.assert_not_called()


def test_search_returns_genes_and_explanation(agent_a, agent_c):
    response = post_search(FakeDriver(records=[BRCA2_RECORD]))

    assert response.status_code == 200
    body = response.json()
    assert body["result_count"] == 1
    assert body["nodes"][0]["name"] == "BRCA2"
    assert body["nodes"][0]["species_name"] == "Homo sapiens"
    assert body["explanation"] == EXPLANATION
    assert body["cypher_used"] == CYPHER
