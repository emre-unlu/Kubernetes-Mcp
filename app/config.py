from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    k8s_namespace: str = os.getenv("K8S_NAMESPACE", "default")
    kubeconfig_path: Optional[str] = os.getenv("KUBECONFIG_PATH") or None
    k8s_context: Optional[str] = os.getenv("K8S_CONTEXT") or None
    k8s_in_cluster: bool = _get_bool("K8S_IN_CLUSTER", False)

    prometheus_url: Optional[str] = os.getenv("PROMETHEUS_URL") or None
    jaeger_url: Optional[str] = os.getenv("JAEGER_URL") or None

    neo4j_uri: Optional[str] = os.getenv("NEO4J_URI") or None
    neo4j_user: Optional[str] = os.getenv("NEO4J_USER") or None
    neo4j_password: Optional[str] = os.getenv("NEO4J_PASSWORD") or None

    http_timeout_seconds: int = int(os.getenv("HTTP_TIMEOUT_SECONDS", "15"))
    shell_timeout_seconds: int = int(os.getenv("SHELL_TIMEOUT_SECONDS", "20"))

    mcp_transport: str = os.getenv("MCP_TRANSPORT", "stdio")
    mcp_host: str = os.getenv("MCP_HOST", "127.0.0.1")
    mcp_port: int = int(os.getenv("MCP_PORT", "8000"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()