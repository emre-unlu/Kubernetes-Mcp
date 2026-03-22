from __future__ import annotations

from app.server import mcp
from app.dependencies import get_trace_service


@mcp.tool()
def get_trace_summaries(
    service_name: str,
    limit: int = 20,
    lookback: str = "15m",
    min_duration_ms: float | None = None,
    only_errors: bool = False,
):
    """Get summarized traces for a service from Jaeger."""
    service = get_trace_service()
    return service.get_trace_summaries(
        service_name=service_name,
        limit=limit,
        lookback=lookback,
        min_duration_ms=min_duration_ms,
        only_errors=only_errors,
    )


@mcp.tool()
def get_trace_details(trace_id: str):
    """Get detailed trace information by trace ID from Jaeger."""
    service = get_trace_service()
    return service.get_trace_details(trace_id)