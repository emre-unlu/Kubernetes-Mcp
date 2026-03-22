from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import requests


logger = logging.getLogger(__name__)


class PrometheusClient:
    """Thin client for Prometheus HTTP API.

    Responsibilities:
    - Execute instant and range PromQL queries
    - Return normalized JSON payloads
    - Provide a few tiny helpers for extracting values
    """

    def __init__(
        self,
        prometheus_url: str,
        timeout_seconds: int = 15,
    ) -> None:
        if not prometheus_url:
            raise ValueError("prometheus_url is required")

        self.prometheus_url = prometheus_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def query(self, promql: str) -> Dict[str, Any]:
        """Run an instant Prometheus query."""
        api_url = f"{self.prometheus_url}/api/v1/query"

        try:
            response = requests.get(
                api_url,
                params={"query": promql},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            logger.exception("Failed to run Prometheus instant query")
            raise RuntimeError(f"Failed to run Prometheus query: {exc}") from exc

        self._validate_success_response(data)
        return data

    def query_range(
        self,
        promql: str,
        start: str,
        end: str,
        step: str = "30s",
    ) -> Dict[str, Any]:
        """Run a range Prometheus query."""
        api_url = f"{self.prometheus_url}/api/v1/query_range"

        try:
            response = requests.get(
                api_url,
                params={
                    "query": promql,
                    "start": start,
                    "end": end,
                    "step": step,
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            logger.exception("Failed to run Prometheus range query")
            raise RuntimeError(f"Failed to run Prometheus range query: {exc}") from exc

        self._validate_success_response(data)
        return data

    @staticmethod
    def extract_results(response_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract raw Prometheus result list."""
        data = response_data.get("data", {})
        results = data.get("result", [])

        if not isinstance(results, list):
            raise RuntimeError("Unexpected Prometheus response format: result is not a list")

        return results

    @staticmethod
    def extract_scalar_value(response_data: Dict[str, Any]) -> Optional[float]:
        """Extract a single scalar-like value from the first instant-vector result."""
        results = PrometheusClient.extract_results(response_data)
        if not results:
            return None

        first = results[0]
        value = first.get("value")

        if not isinstance(value, list) or len(value) < 2:
            return None

        raw_value = value[1]
        try:
            return float(raw_value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def extract_labeled_values(response_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract result rows as metric/value dicts."""
        results = PrometheusClient.extract_results(response_data)

        normalized: List[Dict[str, Any]] = []
        for item in results:
            metric = item.get("metric", {})
            value = item.get("value")

            parsed_value: Optional[float] = None
            timestamp: Optional[Any] = None

            if isinstance(value, list) and len(value) >= 2:
                timestamp = value[0]
                try:
                    parsed_value = float(value[1])
                except (TypeError, ValueError):
                    parsed_value = None

            normalized.append(
                {
                    "metric": metric,
                    "timestamp": timestamp,
                    "value": parsed_value,
                }
            )

        return normalized

    @staticmethod
    def extract_range_series(response_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract matrix results from a range query."""
        results = PrometheusClient.extract_results(response_data)

        normalized: List[Dict[str, Any]] = []
        for item in results:
            metric = item.get("metric", {})
            values = item.get("values", [])

            parsed_points = []
            for point in values:
                if not isinstance(point, list) or len(point) < 2:
                    continue
                try:
                    parsed_points.append(
                        {
                            "timestamp": point[0],
                            "value": float(point[1]),
                        }
                    )
                except (TypeError, ValueError):
                    continue

            normalized.append(
                {
                    "metric": metric,
                    "values": parsed_points,
                }
            )

        return normalized

    @staticmethod
    def _validate_success_response(data: Dict[str, Any]) -> None:
        if not isinstance(data, dict):
            raise RuntimeError("Unexpected Prometheus response format: expected JSON object")

        status = data.get("status")
        if status != "success":
            error_type = data.get("errorType")
            error = data.get("error")
            raise RuntimeError(
                f"Prometheus query failed with status={status}, "
                f"errorType={error_type}, error={error}"
            )