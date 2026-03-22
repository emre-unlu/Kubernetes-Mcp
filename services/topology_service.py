from __future__ import annotations

from typing import Any, Dict, Optional

from clients.base_k8s_client import BaseK8sClient
from clients.neo4j_client import Neo4jClient


class TopologyService:
    """Service layer for cluster topology and service dependency operations.

    Responsibilities:
    - Expose cluster overview from Kubernetes
    - Resolve service -> pods
    - Resolve pod -> services
    - Expose Neo4j dependency and neighborhood lookups
    - Optionally combine Kubernetes existence checks with graph queries
    """

    def __init__(
        self,
        k8s_client: BaseK8sClient,
        neo4j_client: Optional[Neo4jClient] = None,
    ) -> None:
        self.k8s_client = k8s_client
        self.neo4j_client = neo4j_client

    def get_cluster_overview(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """Return a namespace-level overview of services and pods."""
        return self.k8s_client.get_cluster_overview(namespace=namespace)

    def get_pods_from_service(
        self,
        service_name: str,
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return pods selected by a Kubernetes Service."""
        return self.k8s_client.get_pods_from_service(
            service_name=service_name,
            namespace=namespace,
        )

    def get_services_from_pod(
        self,
        pod_name: str,
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return Services whose selectors match the given Pod."""
        return self.k8s_client.get_services_from_pod(
            pod_name=pod_name,
            namespace=namespace,
        )

    def get_service_dependencies(self, service_name: str) -> Dict[str, Any]:
        """Return direct dependencies of a service from Neo4j."""
        self._ensure_graph_client()

        result = self.neo4j_client.get_dependencies(service_name)

        if self._service_exists_in_cluster(service_name):
            result["service_exists_in_cluster"] = True
        else:
            result["service_exists_in_cluster"] = False

        return result

    def get_services_used_by(self, service_name: str) -> Dict[str, Any]:
        """Return incoming dependents / upstream users of a service from Neo4j."""
        self._ensure_graph_client()

        result = self.neo4j_client.get_used_by(service_name)

        if self._service_exists_in_cluster(service_name):
            result["service_exists_in_cluster"] = True
        else:
            result["service_exists_in_cluster"] = False

        return result

    def get_service_map(self, service_name: str, depth: int = 2) -> Dict[str, Any]:
        """Return a bounded dependency neighborhood around a service."""
        self._ensure_graph_client()

        result = self.neo4j_client.get_service_map(service_name=service_name, depth=depth)

        if self._service_exists_in_cluster(service_name):
            result["service_exists_in_cluster"] = True
            k8s_info = self.k8s_client.get_pods_from_service(service_name)
            result["k8s_runtime"] = {
                "namespace": k8s_info.get("namespace"),
                "pods": k8s_info.get("pods", []),
            }
        else:
            result["service_exists_in_cluster"] = False

        return result

    def get_service_topology_summary(
        self,
        service_name: str,
        namespace: Optional[str] = None,
        depth: int = 2,
    ) -> Dict[str, Any]:
        """Combine Kubernetes runtime info with Neo4j dependency info."""
        ns = namespace or self.k8s_client.namespace

        summary: Dict[str, Any] = {
            "service": service_name,
            "namespace": ns,
        }

        k8s_runtime = self.k8s_client.get_pods_from_service(service_name, ns)
        summary["runtime"] = k8s_runtime

        if self.neo4j_client is None:
            summary["graph_info"] = {
                "info": "Neo4j client is not configured."
            }
            return summary

        summary["dependencies"] = self.neo4j_client.get_dependencies(service_name)
        summary["used_by"] = self.neo4j_client.get_used_by(service_name)
        summary["service_map"] = self.neo4j_client.get_service_map(
            service_name=service_name,
            depth=depth,
        )

        return summary

    def _ensure_graph_client(self) -> None:
        if self.neo4j_client is None:
            raise RuntimeError("Neo4j client is not configured")

    def _service_exists_in_cluster(self, service_name: str) -> bool:
        try:
            services = self.k8s_client.get_services_list()
            return service_name in services
        except Exception:
            return False