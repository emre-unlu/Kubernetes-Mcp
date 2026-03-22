from __future__ import annotations

from app.config import get_settings
from app.server import mcp
import tools  # noqa: F401


def main() -> None:
    settings = get_settings()

    if settings.mcp_transport == "streamable-http":
        mcp.run(
            transport="streamable-http",
            host=settings.mcp_host,
            port=settings.mcp_port,
        )
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()