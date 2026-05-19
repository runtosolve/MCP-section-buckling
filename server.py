"""CEE Section Buckling — Remote MCP Server (Streamable HTTP)."""

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import Response

from tools import register_all

security = TransportSecuritySettings(enable_dns_rebinding_protection=False)

# Primary server (SSE mode) — for Claude Desktop / mcp-remote
mcp = FastMCP(
    "CEE Section Buckling",
    host="0.0.0.0",
    port=8000,
    transport_security=security,
)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> Response:
    return Response("OK", media_type="text/plain")


register_all(mcp)


if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "default"
    if mode == "json":
        # JSON response mode for LibreChat (stateless, no SSE)
        import uvicorn

        json_mcp = FastMCP(
            "CEE Section Buckling",
            json_response=True,
            transport_security=security,
        )
        register_all(json_mcp)
        app = json_mcp.streamable_http_app()
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        mcp.run(transport="streamable-http")
