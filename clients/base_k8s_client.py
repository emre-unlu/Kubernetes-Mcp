from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from kubernetes import client, config
from kubernetes.client import CoreV1Api
from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException

logger = logging.getLogger(__name__)


class BaseK8sClient:
    """Base client for Kubernetes CoreV1 operations.

    Responsibilities:
    - Load kube config lazily
    - Expose common pod/service access helpers
    - Provide service <-> pod mapping
    - Provide lightweight cached name lookups
    """

    def __init__(
        self,
        namespace: str = "default",
        kubeconfig_path: Optional[str] = None,
        context: Optional[str] = None,
        in_cluster: bool = False,
    ) -> None:
        self.namespace = namespace
        self.kubeconfig_path = kubeconfig_path
        self.context = context
        self.in_cluster = in_cluster

        self._k8s_client: Optional[CoreV1Api] = None
        self._services_cache: Optional[List[str]] = None
        self._pods_cache: Optional[List[str]] = None

    @property
    def k8s_client(self) -> CoreV1Api:
        """Lazily initialize Kubernetes CoreV1Api client."""
        if self._k8s_client is None:
            try:
                if self.in_cluster:
                    config.load_incluster_config()
                else:
                    if self.kubeconfig_path:
                        config.load_kube_config(
                            config_file=self.kubeconfig_path,
                            context=self.context,
                        )
                    else:
                        config.load_kube_config(context=self.context)

                self._k8s_client = client.CoreV1Api()
            except ConfigException as exc:
                logger.exception("Failed to load Kubernetes configuration")
                raise RuntimeError(
                    "Failed to load Kubernetes configuration. "
                    "Check kubeconfig path, context, or in-cluster settings."
                ) from exc
            except Exception as exc:
                logger.exception("Failed to initialize Kubernetes client")
                raise RuntimeError(
                    f"Failed to initialize Kubernetes CoreV1Api: {exc}"
                ) from exc

        return self._k8s_client

    def refresh_cache(self) -> None:
        """Clear cached pod/service names."""
        self._services_cache = None
        self._pods_cache = None

    def list_services(self, namespace: Optional[str] = None):
        ns = namespace or self.namespace
        return self.k8s_client.list_namespaced_service(ns).items

    def list_pods(self, namespace: Optional[str] = None):
        ns = namespace or self.namespace
        return self.k8s_client.list_namespaced_pod(ns).items

    def get_services_list(
        self,
        namespace: Optional[str] = None,
        use_cache: bool = True,
    ) -> List[str]:
        """Get service names in a namespace, optionally using cache."""
        ns = namespace or self.namespace

        if not use_cache or self._services_cache is None:
            try:
                services = self.k8s_client.list_namespaced_service(ns)
                self._services_cache = [
                    svc.metadata.name
                    for svc in services.items
                    if svc.metadata and svc.metadata.name
                ]
            except ApiException as exc:
                logger.error("Failed to get services list in namespace %s: %s", ns, exc)
                return []
            except Exception as exc:
                logger.exception("Unexpected error while fetching services list")
                return []

        return self._services_cache

    def get_pods_list(
        self,
        namespace: Optional[str] = None,
        use_cache: bool = True,
    ) -> List[str]:
        """Get pod names in a namespace, optionally using cache."""
        ns = namespace or self.namespace

        if not use_cache or self._pods_cache is None:
            try:
                pods = self.k8s_client.list_namespaced_pod(ns)
                self._pods_cache = [
                    pod.metadata.name
                    for pod in pods.items
                    if pod.metadata and pod.metadata.name
                ]
            except ApiException as exc:
                logger.error("Failed to get pods list in namespace %s: %s", ns, exc)
                return []
            except Exception:
                logger.exception("Unexpected error while fetching pods list")
                return []

        return self._pods_cache

    def get_service(self, service_name: str, namespace: Optional[str] = None):
        ns = namespace or self.namespace
        return self.k8s_client.read_namespaced_service(service_name, ns)

    def get_pod(self, pod_name: str, namespace: Optional[str] = None):
        ns = namespace or self.namespace
        return self.k8s_client.read_namespaced_pod(pod_name, ns)

    def get_pods_from_service(
        self,
        service_name: str,
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return pods selected by a service."""
        ns = namespace or self.namespace
        result: Dict[str, Any] = {
            "service_name": service_name,
            "namespace": ns,
            "pods": [],
        }

        try:
            service = self.get_service(service_name, ns)
        except ApiException as exc:
            if exc.status == 404:
                result["error"] = (
                    f"Service '{service_name}' does not exist in namespace '{ns}'."
                )
                return result
            result["error"] = (
                f"Failed to read service '{service_name}' in namespace '{ns}': {exc}"
            )
            return result
        except Exception as exc:
            result["error"] = (
                f"Unexpected error while reading service '{service_name}': {exc}"
            )
            return result

        selector = service.spec.selector if service and service.spec else None
        if not selector:
            result["error"] = f"Service '{service_name}' has no selector configured."
            return result

        label_selector = ",".join(f"{key}={value}" for key, value in selector.items())

        try:
            pods = self.k8s_client.list_namespaced_pod(
                namespace=ns,
                label_selector=label_selector,
            )
            result["pods"] = [
                {
                    "pod_name": pod.metadata.name,
                    "pod_status": pod.status.phase,
                    "pod_ip": pod.status.pod_ip,
                    "node_name": pod.spec.node_name,
                }
                for pod in pods.items
            ]
        except ApiException as exc:
            result["error"] = (
                f"Failed to list pods for service '{service_name}' in namespace '{ns}': {exc}"
            )
        except Exception as exc:
            result["error"] = (
                f"Unexpected error while listing pods for service '{service_name}': {exc}"
            )

        return result

    def get_services_from_pod(
        self,
        pod_name: str,
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return services whose selectors match the pod labels."""
        ns = namespace or self.namespace
        result: Dict[str, Any] = {
            "pod_name": pod_name,
            "namespace": ns,
            "services": [],
        }

        try:
            pod = self.get_pod(pod_name, ns)
        except ApiException as exc:
            if exc.status == 404:
                result["error"] = f"Pod '{pod_name}' does not exist in namespace '{ns}'."
                return result
            result["error"] = f"Failed to read pod '{pod_name}' in namespace '{ns}': {exc}"
            return result
        except Exception as exc:
            result["error"] = f"Unexpected error while reading pod '{pod_name}': {exc}"
            return result

        pod_labels = pod.metadata.labels if pod.metadata else None
        if not pod_labels:
            result["info"] = f"Pod '{pod_name}' has no labels."
            return result

        try:
            services = self.list_services(ns)
            for service in services:
                selector = service.spec.selector if service and service.spec else None
                if not selector:
                    continue

                if all(pod_labels.get(key) == value for key, value in selector.items()):
                    result["services"].append(
                        {
                            "service_name": service.metadata.name,
                            "selector": selector,
                            "service_type": service.spec.type,
                            "cluster_ip": service.spec.cluster_ip,
                        }
                    )

            if not result["services"]:
                result["info"] = f"No services found selecting pod '{pod_name}'."

        except ApiException as exc:
            result["error"] = (
                f"Failed to list services for pod '{pod_name}' in namespace '{ns}': {exc}"
            )
        except Exception as exc:
            result["error"] = (
                f"Unexpected error while finding services for pod '{pod_name}': {exc}"
            )

        return result

    def get_cluster_overview(
        self,
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return a lightweight overview of pods and services in a namespace."""
        ns = namespace or self.namespace

        try:
            pods = self.list_pods(ns)
            services = self.list_services(ns)
        except ApiException as exc:
            return {
                "namespace": ns,
                "pods": [],
                "services": [],
                "error": f"Failed to fetch cluster overview: {exc}",
            }
        except Exception as exc:
            return {
                "namespace": ns,
                "pods": [],
                "services": [],
                "error": f"Unexpected error while fetching cluster overview: {exc}",
            }

        pod_items = [
            {
                "name": pod.metadata.name,
                "phase": pod.status.phase,
                "pod_ip": pod.status.pod_ip,
                "node_name": pod.spec.node_name,
                "labels": pod.metadata.labels or {},
            }
            for pod in pods
        ]

        service_items = []
        for service in services:
            selector = service.spec.selector or {}
            matched_pods = []

            if selector:
                matched_pods = [
                    pod.metadata.name
                    for pod in pods
                    if pod.metadata
                    and pod.metadata.labels
                    and all(
                        pod.metadata.labels.get(key) == value
                        for key, value in selector.items()
                    )
                ]

            service_items.append(
                {
                    "name": service.metadata.name,
                    "type": service.spec.type,
                    "cluster_ip": service.spec.cluster_ip,
                    "selector": selector,
                    "ports": [
                        {
                            "port": port.port,
                            "target_port": str(port.target_port),
                            "protocol": port.protocol,
                        }
                        for port in (service.spec.ports or [])
                    ],
                    "matched_pods": matched_pods,
                }
            )

        return {
            "namespace": ns,
            "pod_count": len(pod_items),
            "service_count": len(service_items),
            "pods": pod_items,
            "services": service_items,
        }