from __future__ import annotations

from app.server import mcp
from app.dependencies import get_shell_service


@mcp.tool()
def exec_shell(command: str):
    """Execute a restricted shell command."""
    service = get_shell_service()
    return service.exec_shell(command)


@mcp.tool()
def exec_kubectl(command: str):
    """Execute a kubectl command only."""
    service = get_shell_service()
    return service.exec_kubectl(command)


@mcp.tool()
def get_shell_policy():
    """Inspect the active shell execution policy."""
    service = get_shell_service()
    return service.get_shell_policy()