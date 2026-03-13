"""
LangGraph StateGraph: Agent A → Neo4j → Agent C

Orchestrates the full search pipeline:
  1. Agent A converts NL query to Cypher
  2. Neo4j executes the Cypher
  3. Agent C generates a persona-aware explanation
  4. Results are assembled into a SearchResponse

Connected to:
  - agent_a_semantic.py: NL → Cypher
  - agent_c_explainer.py: results → explanation
  - api/search.py: called from the POST /api/search endpoint
  - db/queries/search_queries.py: Cypher execution + edge building
"""

from typing import TypedDict, Optional, List
from langgraph.graph import StateGraph, END
import logging

from app.agents.agent_a_semantic import generate_cypher_with_retry
from app.agents.agent_c_explainer import explain_results
from app.db.queries.search_queries import execute_search_cypher, build_edges_from_results

logger = logging.getLogger(__name__)


class SearchState(TypedDict):
    # Inputs
    nl_query: str
    persona: str
    species_filter: Optional[List[str]]
    limit: int
    # Intermediate
    cypher: Optional[str]
    cypher_error: Optional[str]
    raw_results: List[dict]
    edges: List[dict]
    # Output
    explanation: str
    success: bool
    error: Optional[str]


def agent_a_node(state: SearchState) -> SearchState:
    """Node 1: Generate Cypher from NL query."""
    query = state["nl_query"]

    # Append species filter hint if provided
    if state.get("species_filter"):
        taxon_list = str(state["species_filter"])
        query += f"\nRestrict results to species with taxon_ids: {taxon_list}"

    result = generate_cypher_with_retry(query)
    if result["success"]:
        return {**state, "cypher": result["cypher"], "cypher_error": None}
    else:
        return {
            **state,
            "cypher": result["cypher"],
            "cypher_error": result["error"],
            "success": False,
            "error": f"Cypher generation failed: {result['error']}",
        }


def neo4j_node(state: SearchState, driver) -> SearchState:
    """Node 2: Execute Cypher against Neo4j."""
    if not state.get("cypher") or state.get("cypher_error"):
        return state  # Skip if Agent A failed

    try:
        with driver.session() as session:
            raw_results = execute_search_cypher(session, state["cypher"])
            gene_ids = [r.get("gene_id") for r in raw_results if r.get("gene_id")]
            edges = build_edges_from_results(session, gene_ids)

        return {**state, "raw_results": raw_results, "edges": edges}
    except Exception as exc:
        logger.error("Neo4j execution error: %s", exc)
        return {
            **state,
            "raw_results": [],
            "edges": [],
            "success": False,
            "error": f"Query execution error: {exc}",
        }


def agent_c_node(state: SearchState) -> SearchState:
    """Node 3: Generate explanation for results."""
    try:
        explanation = explain_results(
            nl_query=state["nl_query"],
            cypher_query=state.get("cypher", ""),
            results=state["raw_results"],
            persona=state["persona"],
        )
        return {**state, "explanation": explanation, "success": True, "error": None}
    except Exception as exc:
        logger.error("Agent C error: %s", exc)
        return {
            **state,
            "explanation": "Results retrieved. Explanation unavailable.",
            "success": True,
            "error": None,
        }


def build_workflow(driver):
    """
    Build and return a compiled LangGraph workflow.
    The driver is captured in closure for the neo4j_node.
    """
    def neo4j_with_driver(state):
        return neo4j_node(state, driver)

    graph = StateGraph(SearchState)
    graph.add_node("agent_a", agent_a_node)
    graph.add_node("neo4j", neo4j_with_driver)
    graph.add_node("agent_c", agent_c_node)

    graph.set_entry_point("agent_a")
    graph.add_edge("agent_a", "neo4j")
    graph.add_edge("neo4j", "agent_c")
    graph.add_edge("agent_c", END)

    return graph.compile()


async def run_search(
    nl_query: str,
    persona: str,
    species_filter: Optional[List[str]],
    limit: int,
    driver,
) -> SearchState:
    """
    Entry point for the search API endpoint.
    Returns the final SearchState with results + explanation.
    """
    workflow = build_workflow(driver)

    initial_state: SearchState = {
        "nl_query": nl_query,
        "persona": persona,
        "species_filter": species_filter,
        "limit": limit,
        "cypher": None,
        "cypher_error": None,
        "raw_results": [],
        "edges": [],
        "explanation": "",
        "success": False,
        "error": None,
    }

    final_state = await workflow.ainvoke(initial_state)
    return final_state
