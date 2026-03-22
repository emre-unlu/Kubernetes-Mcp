from __future__ import annotations

from app.server import mcp
from app.dependencies import get_logs_service


@mcp.tool()
def get_pod_logs(
    pod_name: str,
    namespace: str | None = None,
    tail_lines: int = 200,
    important_only: bool = True,
):
    service = get_logs_service()
    return service.get_pod_logs(
        pod_name=pod_name,
        namespace=namespace,
        tail_lines=tail_lines,
        important_only=important_only,
    )


@mcp.tool()
def get_service_logs(
    service_name: str,
    namespace: str | None = None,
    tail_lines_per_pod: int = 200,
    important_only: bool = True,
):
    service = get_logs_service()
    return service.get_service_logs(
        service_name=service_name,
        namespace=namespace,
        tail_lines_per_pod=tail_lines_per_pod,
        important_only=important_only,
    )


@mcp.tool()
def summarize_pod_logs(
    pod_name: str,
    namespace: str | None = None,
    tail_lines: int = 200,
):
    service = get_logs_service()
    return service.summarize_pod_logs(
        pod_name=pod_name,
        namespace=namespace,
        tail_lines=tail_lines,
    )


@mcp.tool()
def summarize_service_logs(
    service_name: str,
    namespace: str | None = None,
    tail_lines_per_pod: int = 200,
):
    service = get_logs_service()
    return service.summarize_service_logs(
        service_name=service_name,
        namespace=namespace,
        tail_lines_per_pod=tail_lines_per_pod,
    )