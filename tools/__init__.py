"""Tool registration entrypoint."""

from . import cee_section


def register_all(mcp) -> None:
    """Register every tool on the given FastMCP instance."""
    cee_section.register(mcp)
