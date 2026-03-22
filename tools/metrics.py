from __future__ import annotations

from app.server import mcp
from app.dependencies import get_metrics_service


@mcp.tool()
def get_pod_metrics(pod_name: str, namespace: str | None = None):
    service = get_metrics_service()
    return service.get_pod_metrics(pod_name=pod_name, namespace=namespace)


@mcp.tool()
def get_service_metrics(service_name: str, namespace: str | None = None):
    service = get_metrics_service()
    return service.get_service_metrics(service_name=service_name, namespace=namespace)


@mcp.tool()
def get_pod_triage_metrics(pod_name: str, namespace: str | None = None):
    service = get_metrics_service()
    return service.get_pod_triage_metrics(pod_name=pod_name, namespace=namespace)


@mcp.tool()
def get_service_triage_metrics(service_name: str, namespace: str | None = None):
    service = get_metrics_service()
    return service.get_service_triage_metrics(service_name=service_name, namespace=namespace)