from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


class JaegerClient:
    """Thin client for Jaeger Query API."""

    def __init__(
        self,
        jaeger_url: str,
        timeout_seconds: int = 15,
    ) -> None:
        if not jaeger_url:
            raise ValueError("jaeger_url is required")

        self.jaeger_url = jaeger_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def search_traces(
        self,
        service: str,
        limit: int = 20,
        lookback: str = "15m",
        min_duration_ms: Optional[float] = None,
        only_errors: bool = False,
    ) -> Dict[str, Any]:
        """Fetch traces from Jaeger using query parameters."""
        api_url = f"{self.jaeger_url}/api/traces"

        params: Dict[str, Any] = {
            "service": service,
            "limit": limit,
            "lookback": lookback,
        }

        if min_duration_ms is not None:
            params["minDuration"] = f"{int(min_duration_ms)}ms"

        if only_errors:
            params["tags"] = '{"error":"true"}'

        try:
            response = requests.get(
                api_url,
                params=params,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            logger.exception("Failed to query Jaeger traces")
            raise RuntimeError(f"Failed to query Jaeger traces: {exc}") from exc

        if not isinstance(data, dict):
            raise RuntimeError("Unexpected Jaeger response format: expected JSON object")

        return data

    def get_trace(self, trace_id: str) -> Dict[str, Any]:
        """Fetch a single trace by trace ID."""
        api_url = f"{self.jaeger_url}/api/traces/{trace_id}"

        try:
            response = requests.get(api_url, timeout=self.timeout_seconds)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            logger.exception("Failed to fetch Jaeger trace %s", trace_id)
            raise RuntimeError(f"Failed to fetch Jaeger trace '{trace_id}': {exc}") from exc

        if not isinstance(data, dict):
            raise RuntimeError("Unexpected Jaeger response format: expected JSON object")

        return data

    @staticmethod
    def extract_trace_list(response_data: Dict[str, Any]) -> list[Dict[str, Any]]:
        """Return Jaeger trace list from API response."""
        traces = response_data.get("data", [])
        if not isinstance(traces, list):
            raise RuntimeError("Unexpected Jaeger response format: 'data' is not a list")
        return traces

    @staticmethod
    def extract_single_trace(response_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Return the first trace object from a single-trace response."""
        traces = response_data.get("data", [])
        if not isinstance(traces, list):
            raise RuntimeError("Unexpected Jaeger response format: 'data' is not a list")
        if not traces:
            return None
        return traces[0]