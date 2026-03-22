from __future__ import annotations

from typing import Any, Dict, List, Optional

from clients.base_k8s_client import BaseK8sClient
from clients.prometheus_client import PrometheusClient


class MetricsService:
    """Service layer for pod/service metrics built on Prometheus + Kubernetes.

    Responsibilities:
    - Define the metric catalog we care about
    - Build PromQL queries for pods
    - Aggregate pod metrics into service metrics
    - Expose basic triage-friendly summaries
    """

    def __init__(
        self,
        k8s_client: BaseK8sClient,
        prometheus_client: PrometheusClient,
    ) -> None:
        self.k8s_client = k8s_client
        self.prometheus_client = prometheus_client

        # Instant queries
        self.pod_metric_queries: Dict[str, str] = {
            "cpu_usage_cores": (
                'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}",pod="{pod}",container!="",container!="POD"}}[5m]))'
            ),
            "memory_working_set_bytes": (
                'sum(container_memory_working_set_bytes{{namespace="{namespace}",pod="{pod}",container!="",container!="POD"}})'
            ),
            "restart_count": (
                'sum(kube_pod_container_status_restarts_total{{namespace="{namespace}",pod="{pod}"}})'
            ),
            "network_receive_bytes_per_sec": (
                'sum(rate(container_network_receive_bytes_total{{namespace="{namespace}",pod="{pod}"}}[5m]))'
            ),
            "network_transmit_bytes_per_sec": (
                'sum(rate(container_network_transmit_bytes_total{{namespace="{namespace}",pod="{pod}"}}[5m]))'
            ),
            "network_receive_errors_per_sec": (
                'sum(rate(container_network_receive_errors_total{{namespace="{namespace}",pod="{pod}"}}[5m]))'
            ),
            "network_transmit_errors_per_sec": (
                'sum(rate(container_network_transmit_errors_total{{namespace="{namespace}",pod="{pod}"}}[5m]))'
            ),
        }

        # Range queries
        self.pod_metric_range_queries: Dict[str, str] = {
            "cpu_usage_cores": (
                'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}",pod="{pod}",container!="",container!="POD"}}[5m]))'
            ),
            "memory_working_set_bytes": (
                'sum(container_memory_working_set_bytes{{namespace="{namespace}",pod="{pod}",container!="",container!="POD"}})'
            ),
            "network_receive_bytes_per_sec": (
                'sum(rate(container_network_receive_bytes_total{{namespace="{namespace}",pod="{pod}"}}[5m]))'
            ),
            "network_transmit_bytes_per_sec": (
                'sum(rate(container_network_transmit_bytes_total{{namespace="{namespace}",pod="{pod}"}}[5m]))'
            ),
        }

    def get_pod_metrics(
        self,
        pod_name: str,
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return a fixed set of instant metrics for a pod."""
        ns = namespace or self.k8s_client.namespace

        if not self._pod_exists(pod_name, ns):
            return {
                "pod": pod_name,
                "namespace": ns,
                "metrics": {},
                "error": f"Pod '{pod_name}' does not exist in namespace '{ns}'.",
            }

        results: Dict[str, Any] = {
            "pod": pod_name,
            "namespace": ns,
            "metrics": {},
        }

        for metric_name, query_template in self.pod_metric_queries.items():
            promql = query_template.format(namespace=ns, pod=pod_name)

            try:
                response = self.prometheus_client.query(promql)
                value = self.prometheus_client.extract_scalar_value(response)
                results["metrics"][metric_name] = value
            except Exception as exc:
                results["metrics"][metric_name] = None
                results.setdefault("metric_errors", {})[metric_name] = str(exc)

        return results

    def get_pod_metrics_range(
        self,
        pod_name: str,
        start: str,
        end: str,
        step: str = "30s",
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return time-series metrics for a pod."""
        ns = namespace or self.k8s_client.namespace

        if not self._pod_exists(pod_name, ns):
            return {
                "pod": pod_name,
                "namespace": ns,
                "start": start,
                "end": end,
                "step": step,
                "series": {},
                "error": f"Pod '{pod_name}' does not exist in namespace '{ns}'.",
            }

        results: Dict[str, Any] = {
            "pod": pod_name,
            "namespace": ns,
            "start": start,
            "end": end,
            "step": step,
            "series": {},
        }

        for metric_name, query_template in self.pod_metric_range_queries.items():
            promql = query_template.format(namespace=ns, pod=pod_name)

            try:
                response = self.prometheus_client.query_range(
                    promql=promql,
                    start=start,
                    end=end,
                    step=step,
                )
                series = self.prometheus_client.extract_range_series(response)
                results["series"][metric_name] = series
            except Exception as exc:
                results["series"][metric_name] = []
                results.setdefault("metric_errors", {})[metric_name] = str(exc)

        return results

    def get_service_metrics(
        self,
        service_name: str,
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return aggregated instant metrics for all pods selected by a service."""
        ns = namespace or self.k8s_client.namespace
        service_runtime = self.k8s_client.get_pods_from_service(service_name, ns)

        if service_runtime.get("error"):
            return {
                "service": service_name,
                "namespace": ns,
                "pods": [],
                "aggregated_metrics": {},
                "error": service_runtime["error"],
            }

        pod_entries = service_runtime.get("pods", [])
        pod_names = [item["pod_name"] for item in pod_entries if item.get("pod_name")]

        if not pod_names:
            return {
                "service": service_name,
                "namespace": ns,
                "pods": [],
                "aggregated_metrics": {},
                "info": f"No pods found for service '{service_name}' in namespace '{ns}'.",
            }

        pod_metrics: List[Dict[str, Any]] = []
        for pod_name in pod_names:
            pod_metrics.append(self.get_pod_metrics(pod_name, ns))

        aggregated = self._aggregate_pod_metrics(pod_metrics)

        return {
            "service": service_name,
            "namespace": ns,
            "pods": pod_names,
            "pod_metrics": pod_metrics,
            "aggregated_metrics": aggregated,
        }

    def get_service_metrics_range(
        self,
        service_name: str,
        start: str,
        end: str,
        step: str = "30s",
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return pod-level range metrics for all pods selected by a service."""
        ns = namespace or self.k8s_client.namespace
        service_runtime = self.k8s_client.get_pods_from_service(service_name, ns)

        if service_runtime.get("error"):
            return {
                "service": service_name,
                "namespace": ns,
                "start": start,
                "end": end,
                "step": step,
                "pods": [],
                "series_by_pod": {},
                "error": service_runtime["error"],
            }

        pod_entries = service_runtime.get("pods", [])
        pod_names = [item["pod_name"] for item in pod_entries if item.get("pod_name")]

        if not pod_names:
            return {
                "service": service_name,
                "namespace": ns,
                "start": start,
                "end": end,
                "step": step,
                "pods": [],
                "series_by_pod": {},
                "info": f"No pods found for service '{service_name}' in namespace '{ns}'.",
            }

        series_by_pod: Dict[str, Any] = {}
        for pod_name in pod_names:
            series_by_pod[pod_name] = self.get_pod_metrics_range(
                pod_name=pod_name,
                namespace=ns,
                start=start,
                end=end,
                step=step,
            )

        return {
            "service": service_name,
            "namespace": ns,
            "start": start,
            "end": end,
            "step": step,
            "pods": pod_names,
            "series_by_pod": series_by_pod,
        }

    def get_pod_triage_metrics(
        self,
        pod_name: str,
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return a small triage-oriented summary for a pod."""
        pod_metrics = self.get_pod_metrics(pod_name, namespace)
        metrics = pod_metrics.get("metrics", {})

        cpu = metrics.get("cpu_usage_cores")
        memory = metrics.get("memory_working_set_bytes")
        restarts = metrics.get("restart_count")
        rx_err = metrics.get("network_receive_errors_per_sec")
        tx_err = metrics.get("network_transmit_errors_per_sec")

        signals: List[str] = []

        if restarts is not None and restarts > 0:
            signals.append("pod_has_restarts")
        if rx_err is not None and rx_err > 0:
            signals.append("network_receive_errors_detected")
        if tx_err is not None and tx_err > 0:
            signals.append("network_transmit_errors_detected")
        if cpu is not None and cpu > 1.0:
            signals.append("high_cpu_usage")
        if memory is not None and memory > 1_000_000_000:
            signals.append("high_memory_usage")

        pod_metrics["triage"] = {
            "signals": signals,
            "signal_count": len(signals),
            "looks_suspicious": len(signals) > 0,
        }

        return pod_metrics

    def get_service_triage_metrics(
        self,
        service_name: str,
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return triage-oriented metrics for all pods behind a service."""
        ns = namespace or self.k8s_client.namespace
        service_runtime = self.k8s_client.get_pods_from_service(service_name, ns)

        if service_runtime.get("error"):
            return {
                "service": service_name,
                "namespace": ns,
                "pods": [],
                "error": service_runtime["error"],
            }

        pod_entries = service_runtime.get("pods", [])
        pod_names = [item["pod_name"] for item in pod_entries if item.get("pod_name")]

        triage_results = [self.get_pod_triage_metrics(pod_name, ns) for pod_name in pod_names]

        suspicious_pods = [
            item["pod"]
            for item in triage_results
            if item.get("triage", {}).get("looks_suspicious")
        ]

        return {
            "service": service_name,
            "namespace": ns,
            "pods": pod_names,
            "suspicious_pods": suspicious_pods,
            "triage_results": triage_results,
        }

    def _aggregate_pod_metrics(self, pod_metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate pod metrics into service-level summary values."""
        cpu_values: List[float] = []
        memory_values: List[float] = []
        restart_values: List[float] = []
        rx_values: List[float] = []
        tx_values: List[float] = []
        rx_err_values: List[float] = []
        tx_err_values: List[float] = []

        for pod_result in pod_metrics:
            metrics = pod_result.get("metrics", {})

            self._append_if_number(cpu_values, metrics.get("cpu_usage_cores"))
            self._append_if_number(memory_values, metrics.get("memory_working_set_bytes"))
            self._append_if_number(restart_values, metrics.get("restart_count"))
            self._append_if_number(rx_values, metrics.get("network_receive_bytes_per_sec"))
            self._append_if_number(tx_values, metrics.get("network_transmit_bytes_per_sec"))
            self._append_if_number(rx_err_values, metrics.get("network_receive_errors_per_sec"))
            self._append_if_number(tx_err_values, metrics.get("network_transmit_errors_per_sec"))

        return {
            "cpu_usage_cores_sum": sum(cpu_values) if cpu_values else None,
            "memory_working_set_bytes_sum": sum(memory_values) if memory_values else None,
            "restart_count_sum": sum(restart_values) if restart_values else None,
            "restart_count_max": max(restart_values) if restart_values else None,
            "network_receive_bytes_per_sec_sum": sum(rx_values) if rx_values else None,
            "network_transmit_bytes_per_sec_sum": sum(tx_values) if tx_values else None,
            "network_receive_errors_per_sec_sum": sum(rx_err_values) if rx_err_values else None,
            "network_transmit_errors_per_sec_sum": sum(tx_err_values) if tx_err_values else None,
            "pod_count_with_metrics": len(pod_metrics),
        }

    @staticmethod
    def _append_if_number(target: List[float], value: Any) -> None:
        if isinstance(value, (int, float)):
            target.append(float(value))

    def _pod_exists(self, pod_name: str, namespace: str) -> bool:
        try:
            pods = self.k8s_client.get_pods_list(namespace=namespace)
            return pod_name in pods
        except Exception:
            return False