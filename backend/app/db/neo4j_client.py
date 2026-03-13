"""
Neo4j AuraDB driver singleton.

Creates a single driver instance at application startup and reuses it
for all queries. The driver manages an internal connection pool.

Connected to:
  - app/main.py: driver created in lifespan startup, closed on shutdown
  - app/dependencies.py: get_neo4j_session() yields sessions from this driver
  - app/db/schema.py: init_schema() called during lifespan startup
"""

from neo4j import GraphDatabase, Driver
from app.config import settings
import logging

logger = logging.getLogger(__name__)

_driver: Driver | None = None


def get_driver() -> Driver:
    """Return the global Neo4j driver, creating it if needed."""
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        logger.info("Neo4j driver initialised — %s", settings.neo4j_uri)
    return _driver


def close_driver() -> None:
    """Close the driver. Called during application shutdown."""
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
        logger.info("Neo4j driver closed")


def verify_connectivity() -> bool:
    """Return True if Neo4j is reachable, False otherwise."""
    try:
        get_driver().verify_connectivity()
        return True
    except Exception as exc:
        logger.error("Neo4j connectivity check failed: %s", exc)
        return False
