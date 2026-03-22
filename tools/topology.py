from __future__ import annotations

from app.server import mcp
from app.dependencies import get_topology_service


@mcp.tool()
def get_cluster_overview(namespace: str | None = None):
    """Get a namespace overview of pods and services."""
    service = get_topology_service()
    return service.get_cluster_overview(namespace=namespace)


@mcp.tool()
def get_pods_from_service(service_name: str, namespace: str | None = None):
    """Get pods selected by a Kubernetes Service."""
    service = get_topology_service()
    return service.get_pods_from_service(service_name=service_name, namespace=namespace)


@mcp.tool()
def get_services_from_pod(pod_name: str, namespace: str | None = None):
    """Get Services that select the given Pod."""
    service = get_topology_service()
    return service.get_services_from_pod(pod_name=pod_name, namespace=namespace)


@mcp.tool()
def get_service_dependencies(service_name: str):
    """Get direct service dependencies from Neo4j."""
    service = get_topology_service()
    return service.get_service_dependencies(service_name=service_name)


@mcp.tool()
def get_services_used_by(service_name: str):
    """Get services that depend on the given service from Neo4j."""
    service = get_topology_service()
    return service.get_services_used_by(service_name=service_name)


@mcp.tool()
def get_service_map(service_name: str, depth: int = 2):
    """Get bounded dependency neighborhood around a service."""
    service = get_topology_service()
    return service.get_service_map(service_name=service_name, depth=depth)


@mcp.tool()
def get_service_topology_summary(
    service_name: str,
    namespace: str | None = None,
    depth: int = 2,
):
    """Get combined runtime + graph topology summary for a service."""
    service = get_topology_service()
    return service.get_service_topology_summary(
        service_name=service_name,
        namespace=namespace,
        depth=depth,
    )