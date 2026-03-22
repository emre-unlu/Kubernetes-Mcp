from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from clients.jaeger_client import JaegerClient
from clients.neo4j_client import Neo4jClient
from clients.prometheus_client import PrometheusClient
from clients.shell_client import ShellClient
from services.metrics_service import MetricsService
from services.shell_service import ShellService
from services.topology_service import TopologyService
from services.trace_service import TraceService
from clients.base_k8s_client import BaseK8sClient
from services.logs_service import LogsService
from services.shell_service import ShellService


@lru_cache(maxsize=1)
def get_prometheus_client() -> PrometheusClient:
    settings = get_settings()
    if not settings.prometheus_url:
        raise RuntimeError("PROMETHEUS_URL is not configured")
    return PrometheusClient(
        prometheus_url=settings.prometheus_url,
        timeout_seconds=settings.http_timeout_seconds,
    )

@lru_cache(maxsize=1)
def get_k8s_client() -> BaseK8sClient:
    settings = get_settings()
    return BaseK8sClient(
        namespace=settings.k8s_namespace,
        kubeconfig_path=settings.kubeconfig_path,
        context=settings.k8s_context,
        in_cluster=settings.k8s_in_cluster,
    )



@lru_cache(maxsize=1)
def get_jaeger_client() -> JaegerClient:
    settings = get_settings()
    if not settings.jaeger_url:
        raise RuntimeError("JAEGER_URL is not configured")
    return JaegerClient(
        jaeger_url=settings.jaeger_url,
        timeout_seconds=settings.http_timeout_seconds,
    )

@lru_cache(maxsize=1)
def get_neo4j_client() -> Neo4jClient:
    settings = get_settings()
    if not settings.neo4j_uri or not settings.neo4j_user or not settings.neo4j_password:
        raise RuntimeError("Neo4j settings are incomplete")
    return Neo4jClient(
        uri=settings.neo4j_uri,
        username=settings.neo4j_user,
        password=settings.neo4j_password,
    )

@lru_cache(maxsize=1)
def get_shell_client() -> ShellClient:
    settings = get_settings()
    return ShellClient(
        timeout_seconds=settings.shell_timeout_seconds,
    )

@lru_cache(maxsize=1)
def get_shell_service() -> ShellService:
    return ShellService(
        shell_client=get_shell_client(),
    )


@lru_cache(maxsize=1)
def get_trace_service() -> TraceService:
    return TraceService(jaeger_client=get_jaeger_client())


@lru_cache(maxsize=1)
def get_topology_service() -> TopologyService:
    try:
        neo4j_client = get_neo4j_client()
    except Exception:
        neo4j_client = None

    return TopologyService(
        k8s_client=get_k8s_client(),
        neo4j_client=neo4j_client,
    )

@lru_cache(maxsize=1)
def get_metrics_service() -> MetricsService:
    return MetricsService(
        k8s_client=get_k8s_client(),
        prometheus_client=get_prometheus_client(),
    )



@lru_cache(maxsize=1)
def get_logs_service() -> LogsService:
    return LogsService(
        k8s_client=get_k8s_client(),
    )

@lru_cache(maxsize=1)
def get_shell_service() -> ShellService:
    return ShellService(
        shell_client=get_shell_client(),
    )