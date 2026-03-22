from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from neo4j import Driver, GraphDatabase
from neo4j.exceptions import Neo4jError


logger = logging.getLogger(__name__)


class Neo4jClient:
    """Thin client for Neo4j service/dependency graph queries.

    Responsibilities:
    - Open Neo4j driver
    - Execute Cypher queries safely
    - Return normalized records
    - Expose small graph-specific helper methods
    """

    def __init__(
        self,
        uri: str,
        username: str,
        password: str,
        database: Optional[str] = None,
    ) -> None:
        if not uri:
            raise ValueError("Neo4j uri is required")
        if not username:
            raise ValueError("Neo4j username is required")
        if not password:
            raise ValueError("Neo4j password is required")

        self.uri = uri
        self.username = username
        self.password = password
        self.database = database

        self._driver: Optional[Driver] = None

    @property
    def driver(self) -> Driver:
        """Lazily initialize Neo4j driver."""
        if self._driver is None:
            try:
                self._driver = GraphDatabase.driver(
                    self.uri,
                    auth=(self.username, self.password),
                )
                self._driver.verify_connectivity()
            except Exception as exc:
                logger.exception("Failed to initialize Neo4j driver")
                raise RuntimeError(f"Failed to connect to Neo4j: {exc}") from exc

        return self._driver

    def close(self) -> None:
        """Close the underlying Neo4j driver."""
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def run_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Run a Cypher query and return rows as plain dicts."""
        parameters = parameters or {}

        try:
            if self.database:
                with self.driver.session(database=self.database) as session:
                    result = session.run(query, parameters)
                    return [record.data() for record in result]
            else:
                with self.driver.session() as session:
                    result = session.run(query, parameters)
                    return [record.data() for record in result]
        except Neo4jError as exc:
            logger.exception("Neo4j query failed")
            raise RuntimeError(f"Neo4j query failed: {exc}") from exc
        except Exception as exc:
            logger.exception("Unexpected Neo4j query error")
            raise RuntimeError(f"Unexpected Neo4j query error: {exc}") from exc

    def get_dependencies(self, service_name: str) -> Dict[str, Any]:
        """Return direct outgoing dependencies of a service.

        Expected graph patterns:
        (:Service {name})-[:DEPENDS_ON]->(...)
        (:Service {name})-[:USES]->(...)
        (:Service {name})-[:CALLS]->(:Service)
        """
        query = """
        MATCH (s:Service {name: $service_name})
        OPTIONAL MATCH (s)-[r:DEPENDS_ON|USES|CALLS]->(d)
        RETURN
            s.name AS service,
            type(r) AS relationship,
            labels(d) AS dependency_labels,
            d.name AS dependency_name
        ORDER BY relationship, dependency_name
        """

        rows = self.run_query(query, {"service_name": service_name})

        result: Dict[str, Any] = {
            "service": service_name,
            "dependencies": [],
        }

        if not rows:
            result["info"] = f"No dependencies found for service '{service_name}'."
            return result

        for row in rows:
            dep_name = row.get("dependency_name")
            rel = row.get("relationship")

            if dep_name is None or rel is None:
                continue

            labels = row.get("dependency_labels") or []
            dep_type = self._normalize_node_type(labels)

            result["dependencies"].append(
                {
                    "name": dep_name,
                    "relationship": rel,
                    "type": dep_type,
                }
            )

        if not result["dependencies"]:
            result["info"] = f"No dependencies found for service '{service_name}'."

        return result

    def get_used_by(self, service_name: str) -> Dict[str, Any]:
        """Return direct incoming dependents of a service."""
        query = """
        MATCH (s:Service {name: $service_name})
        OPTIONAL MATCH (u)-[r:DEPENDS_ON|USES|CALLS]->(s)
        RETURN
            s.name AS service,
            type(r) AS relationship,
            labels(u) AS user_labels,
            u.name AS user_name
        ORDER BY relationship, user_name
        """

        rows = self.run_query(query, {"service_name": service_name})

        result: Dict[str, Any] = {
            "service": service_name,
            "used_by": [],
        }

        if not rows:
            result["info"] = f"No upstream services found for '{service_name}'."
            return result

        for row in rows:
            user_name = row.get("user_name")
            rel = row.get("relationship")

            if user_name is None or rel is None:
                continue

            labels = row.get("user_labels") or []
            node_type = self._normalize_node_type(labels)

            result["used_by"].append(
                {
                    "name": user_name,
                    "relationship": rel,
                    "type": node_type,
                }
            )

        if not result["used_by"]:
            result["info"] = f"No upstream services found for '{service_name}'."

        return result

    def get_service_map(self, service_name: str, depth: int = 2) -> Dict[str, Any]:
        """Return neighborhood map around a service up to a bounded depth."""
        if depth < 1:
            raise ValueError("depth must be at least 1")
        if depth > 5:
            raise ValueError("depth must be <= 5 to avoid overly large traversals")

        query = f"""
        MATCH p=(s:Service {{name: $service_name}})-[:DEPENDS_ON|USES|CALLS*1..{depth}]-(n)
        UNWIND relationships(p) AS rel
        WITH DISTINCT
            startNode(rel) AS source,
            endNode(rel) AS target,
            type(rel) AS relationship
        RETURN
            source.name AS source_name,
            labels(source) AS source_labels,
            relationship,
            target.name AS target_name,
            labels(target) AS target_labels
        ORDER BY source_name, relationship, target_name
        """

        rows = self.run_query(query, {"service_name": service_name})

        result: Dict[str, Any] = {
            "service": service_name,
            "depth": depth,
            "edges": [],
        }

        if not rows:
            result["info"] = (
                f"No service map relationships found for '{service_name}' within depth {depth}."
            )
            return result

        seen = set()
        for row in rows:
            source_name = row.get("source_name")
            target_name = row.get("target_name")
            relationship = row.get("relationship")

            if not source_name or not target_name or not relationship:
                continue

            edge_key = (source_name, relationship, target_name)
            if edge_key in seen:
                continue
            seen.add(edge_key)

            result["edges"].append(
                {
                    "source": {
                        "name": source_name,
                        "type": self._normalize_node_type(row.get("source_labels") or []),
                    },
                    "relationship": relationship,
                    "target": {
                        "name": target_name,
                        "type": self._normalize_node_type(row.get("target_labels") or []),
                    },
                }
            )

        if not result["edges"]:
            result["info"] = (
                f"No service map relationships found for '{service_name}' within depth {depth}."
            )

        return result

    def service_exists(self, service_name: str) -> bool:
        """Check whether a Service node exists in the graph."""
        query = """
        MATCH (s:Service {name: $service_name})
        RETURN s.name AS name
        LIMIT 1
        """
        rows = self.run_query(query, {"service_name": service_name})
        return len(rows) > 0

    @staticmethod
    def _normalize_node_type(labels: List[str]) -> str:
        if not labels:
            return "unknown"

        preferred_order = ["Service", "Database", "Cache", "Queue", "Topic", "External"]
        for label in preferred_order:
            if label in labels:
                return label.lower()

        return labels[0].lower()