from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from kubernetes.client.exceptions import ApiException

from clients.base_k8s_client import BaseK8sClient


class LogsService:
    """Service layer for pod and service log retrieval.

    Responsibilities:
    - Read pod logs from Kubernetes
    - Expand service logs by resolving service -> pods
    - Filter important lines for LLM-friendly summaries
    - Return structured grouped results
    """

    IMPORTANT_PATTERNS = [
        r"\berror\b",
        r"\bwarn(?:ing)?\b",
        r"\bcritical\b",
        r"\bfatal\b",
        r"\bpanic\b",
        r"\bexception\b",
        r"\btraceback\b",
        r"\bfailed\b",
        r"\bfailure\b",
        r"\btimeout\b",
        r"\btimed out\b",
        r"\bconnection refused\b",
        r"\bconnection reset\b",
        r"\bunavailable\b",
        r"\boomkilled\b",
        r"\bcrashloopbackoff\b",
        r"\bimagepullbackoff\b",
        r"\bback[- ]off\b",
        r"\b503\b",
        r"\b502\b",
        r"\b500\b",
        r"\b504\b",
    ]

    def __init__(self, k8s_client: BaseK8sClient) -> None:
        self.k8s_client = k8s_client
        self._important_regexes = [
            re.compile(pattern, flags=re.IGNORECASE) for pattern in self.IMPORTANT_PATTERNS
        ]

    def get_pod_logs(
        self,
        pod_name: str,
        namespace: Optional[str] = None,
        tail_lines: int = 200,
        important_only: bool = True,
        container: Optional[str] = None,
        previous: bool = False,
    ) -> Dict[str, Any]:
        """Get logs for a single pod."""
        ns = namespace or self.k8s_client.namespace

        if not self._pod_exists(pod_name, ns):
            return {
                "pod": pod_name,
                "namespace": ns,
                "tail_lines": tail_lines,
                "important_only": important_only,
                "lines": [],
                "error": f"Pod '{pod_name}' does not exist in namespace '{ns}'.",
            }

        try:
            raw_logs = self.k8s_client.k8s_client.read_namespaced_pod_log(
                name=pod_name,
                namespace=ns,
                tail_lines=tail_lines,
                container=container,
                previous=previous,
                timestamps=True,
            )
        except ApiException as exc:
            return {
                "pod": pod_name,
                "namespace": ns,
                "tail_lines": tail_lines,
                "important_only": important_only,
                "lines": [],
                "error": f"Failed to read logs for pod '{pod_name}': {exc}",
            }
        except Exception as exc:
            return {
                "pod": pod_name,
                "namespace": ns,
                "tail_lines": tail_lines,
                "important_only": important_only,
                "lines": [],
                "error": f"Unexpected error while reading logs for pod '{pod_name}': {exc}",
            }

        all_lines = self._split_log_lines(raw_logs)
        lines = (
            self._filter_important_lines(all_lines)
            if important_only
            else all_lines
        )

        return {
            "pod": pod_name,
            "namespace": ns,
            "tail_lines": tail_lines,
            "important_only": important_only,
            "container": container,
            "previous": previous,
            "line_count": len(lines),
            "lines": lines,
        }

    def get_service_logs(
        self,
        service_name: str,
        namespace: Optional[str] = None,
        tail_lines_per_pod: int = 200,
        important_only: bool = True,
        previous: bool = False,
    ) -> Dict[str, Any]:
        """Get logs for all pods selected by a service."""
        ns = namespace or self.k8s_client.namespace

        service_runtime = self.k8s_client.get_pods_from_service(service_name, ns)
        if service_runtime.get("error"):
            return {
                "service": service_name,
                "namespace": ns,
                "tail_lines_per_pod": tail_lines_per_pod,
                "important_only": important_only,
                "pods": {},
                "error": service_runtime["error"],
            }

        pod_entries = service_runtime.get("pods", [])
        pod_names = [item["pod_name"] for item in pod_entries if item.get("pod_name")]

        if not pod_names:
            return {
                "service": service_name,
                "namespace": ns,
                "tail_lines_per_pod": tail_lines_per_pod,
                "important_only": important_only,
                "pods": {},
                "info": f"No pods found for service '{service_name}' in namespace '{ns}'.",
            }

        grouped_logs: Dict[str, Any] = {}
        for pod_name in pod_names:
            grouped_logs[pod_name] = self.get_pod_logs(
                pod_name=pod_name,
                namespace=ns,
                tail_lines=tail_lines_per_pod,
                important_only=important_only,
                previous=previous,
            )

        return {
            "service": service_name,
            "namespace": ns,
            "tail_lines_per_pod": tail_lines_per_pod,
            "important_only": important_only,
            "pod_count": len(pod_names),
            "pods": grouped_logs,
        }

    def summarize_pod_logs(
        self,
        pod_name: str,
        namespace: Optional[str] = None,
        tail_lines: int = 200,
    ) -> Dict[str, Any]:
        """Return a small triage-friendly summary of pod logs."""
        result = self.get_pod_logs(
            pod_name=pod_name,
            namespace=namespace,
            tail_lines=tail_lines,
            important_only=True,
        )

        if result.get("error"):
            return result

        lines: List[str] = result.get("lines", [])
        severity_counts = self._count_severities(lines)

        result["summary"] = {
            "important_line_count": len(lines),
            "severity_counts": severity_counts,
            "looks_suspicious": len(lines) > 0,
        }
        return result

    def summarize_service_logs(
        self,
        service_name: str,
        namespace: Optional[str] = None,
        tail_lines_per_pod: int = 200,
    ) -> Dict[str, Any]:
        """Return a small triage-friendly summary of service logs."""
        result = self.get_service_logs(
            service_name=service_name,
            namespace=namespace,
            tail_lines_per_pod=tail_lines_per_pod,
            important_only=True,
        )

        if result.get("error"):
            return result

        pods = result.get("pods", {})
        suspicious_pods: List[str] = []
        total_important_lines = 0
        aggregate_counts = {
            "error": 0,
            "warning": 0,
            "critical": 0,
            "timeout": 0,
        }

        for pod_name, pod_result in pods.items():
            lines = pod_result.get("lines", [])
            if lines:
                suspicious_pods.append(pod_name)

            total_important_lines += len(lines)
            counts = self._count_severities(lines)
            for key in aggregate_counts:
                aggregate_counts[key] += counts.get(key, 0)

        result["summary"] = {
            "suspicious_pods": suspicious_pods,
            "suspicious_pod_count": len(suspicious_pods),
            "important_line_count": total_important_lines,
            "severity_counts": aggregate_counts,
            "looks_suspicious": total_important_lines > 0,
        }
        return result

    @staticmethod
    def _split_log_lines(raw_logs: str) -> List[str]:
        if not raw_logs:
            return []
        return [line for line in raw_logs.splitlines() if line.strip()]

    def _filter_important_lines(self, lines: List[str]) -> List[str]:
        filtered: List[str] = []
        seen = set()

        for line in lines:
            if self._is_important_line(line):
                normalized = line.strip()
                if normalized not in seen:
                    filtered.append(normalized)
                    seen.add(normalized)

        return filtered

    def _is_important_line(self, line: str) -> bool:
        return any(regex.search(line) for regex in self._important_regexes)

    @staticmethod
    def _count_severities(lines: List[str]) -> Dict[str, int]:
        counts = {
            "error": 0,
            "warning": 0,
            "critical": 0,
            "timeout": 0,
        }

        for line in lines:
            lower = line.lower()
            if "error" in lower or "exception" in lower or "failed" in lower:
                counts["error"] += 1
            if "warn" in lower:
                counts["warning"] += 1
            if "critical" in lower or "fatal" in lower or "panic" in lower:
                counts["critical"] += 1
            if "timeout" in lower or "timed out" in lower:
                counts["timeout"] += 1

        return counts

    def _pod_exists(self, pod_name: str, namespace: str) -> bool:
        try:
            pods = self.k8s_client.get_pods_list(namespace=namespace)
            return pod_name in pods
        except Exception:
            return False