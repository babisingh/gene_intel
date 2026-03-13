"""
FastAPI dependency injection: Neo4j driver, LLM client.

Usage in endpoints:
    from app.dependencies import get_neo4j_driver

    @router.get("/example")
    def example(driver = Depends(get_neo4j_driver)):
        ...
"""

from typing import Generator
from neo4j import Driver
from app.db.neo4j_client import get_driver


def get_neo4j_driver() -> Driver:
    """Return the singleton Neo4j driver."""
    return get_driver()


def get_neo4j_session(driver: Driver = None) -> Generator:
    """
    Yield a Neo4j session and close it after the request.
    Use get_neo4j_driver directly for workflows that manage their own sessions.
    """
    if driver is None:
        driver = get_driver()
    with driver.session() as session:
        yield session
