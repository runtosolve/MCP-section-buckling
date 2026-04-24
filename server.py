"""CEE Section Buckling — Remote MCP Server (Streamable HTTP)."""

import os
import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

CEE_BACKEND_URL = os.environ.get("CEE_BACKEND_URL", "http://localhost:8081")

# Raw eigenvector displacements are normalized so max|Δ| maps to this
# fraction of the section's smaller span. Large enough to show the
# buckling shape, small enough not to distort the section outline.
MODE_SHAPE_VISUALIZATION_RATIO = 0.15

security = TransportSecuritySettings(enable_dns_rebinding_protection=False)

# Primary server (SSE mode) — for Claude Desktop / mcp-remote
mcp = FastMCP(
    "CEE Section Buckling",
    host="0.0.0.0",
    port=8000,
    transport_security=security,
)


def _compose_deformed_shape(mode_shape: dict) -> dict:
    """Combine undeformed coordinates with eigenvector displacements.

    Newer backends return `{X, Y, ΔX, ΔY}` — X/Y is the undeformed wall
    centerline and ΔX/ΔY is the raw buckling eigenvector. The actual
    buckling shape is X + ΔX·scale, Y + ΔY·scale, with scale chosen so
    the deformation is visible against the section dimensions.

    Older backends return only `{X, Y}` with the displacement already
    composed in (though at a fixed 0.5× scale that halves the section).
    In that case we pass the coordinates through unchanged.
    """
    X = mode_shape["X"]
    Y = mode_shape["Y"]
    dX = mode_shape.get("\u0394X")
    dY = mode_shape.get("\u0394Y")

    if dX is None or dY is None:
        return {"X": list(X), "Y": list(Y)}

    max_delta = max(
        max((abs(v) for v in dX), default=0.0),
        max((abs(v) for v in dY), default=0.0),
    )
    if max_delta == 0.0:
        return {"X": list(X), "Y": list(Y)}

    x_span = max(X) - min(X)
    y_span = max(Y) - min(Y)
    scale = MODE_SHAPE_VISUALIZATION_RATIO * min(x_span, y_span) / max_delta

    return {
        "X": [x + dx * scale for x, dx in zip(X, dX)],
        "Y": [y + dy * scale for y, dy in zip(Y, dY)],
    }


@mcp.tool()
def calculate_cee_buckling(
    H: float,
    B: float,
    t: float,
    L: float,
    r: float = None,
    E: float = None,
    nu: float = 0.3,
    units: str = "mm",
) -> dict:
    """
    Calculate elastic buckling loads for a cold-formed C-section (Cee section).

    This tool performs finite-strip analysis to determine local and distortional
    buckling critical loads for cold-formed steel Cee sections.

    Supports both metric (mm) and imperial (inch) unit systems.

    Args:
        H: Web height
        B: Flange width
        t: Thickness
        L: Lip dimension
        r: Inside corner radius. Default: 2.0 mm or 0.0625 inch
        E: Young's modulus. Default: 203000 MPa or 29500 ksi
        nu: Poisson's ratio, default 0.3 (steel)
        units: Unit system — "mm" (metric) or "inch" (imperial).
               When "mm": dimensions in mm, E in MPa, results in N.
               When "inch": dimensions in inches, E in ksi, results in kips.

    Returns:
        dict with:
        - Pcrl: local buckling critical load
        - Pcrd: distortional buckling critical load
        - units: the unit system used (mm/N or inch/kips)
        - local_buckling_mode_shape: {"X": [...], "Y": [...]} — flat 1D lists of
          floats tracing the deformed wall centerline of the LOCAL buckling mode.
        - distortional_buckling_mode_shape: same structure for the DISTORTIONAL mode.

        The X and Y arrays are flat 1D sequences of floats (NOT 2D strip arrays)
        representing a single continuous poly-line along the wall centerline,
        with the buckling displacement already composed in at a visualization-
        friendly scale. Length of X equals length of Y.

        IMPORTANT: after calling this tool, always plot both mode shapes side by
        side with `execute_python`. A minimal correct plot is:

            import matplotlib.pyplot as plt
            fig, axes = plt.subplots(1, 2, figsize=(10, 6))
            for ax, ms, title, load in [
                (axes[0], result["local_buckling_mode_shape"], "Local", result["Pcrl"]),
                (axes[1], result["distortional_buckling_mode_shape"], "Distortional", result["Pcrd"]),
            ]:
                ax.plot(ms["X"], ms["Y"], "-")
                ax.set_aspect("equal")
                ax.set_title(f"{title} buckling\\nPcr = {load:.3f}")

        Do NOT rescale the coordinates, do NOT set xlim/ylim, do NOT slice the
        arrays, do NOT try to treat them as 2D. Just plot X vs Y as one line
        per mode with equal aspect ratio and matplotlib will frame it correctly.
    """
    is_inch = units.lower().startswith("in")
    if r is None:
        r = 0.0625 if is_inch else 2.0
    if E is None:
        E = 29500.0 if is_inch else 203000.0

    payload = {"H": H, "B": B, "t": t, "L": L, "r": r, "E": E, "nu": nu}
    with httpx.Client() as client:
        resp = client.post(f"{CEE_BACKEND_URL}/calculate", json=payload, timeout=120)
        resp.raise_for_status()
        result = resp.json()

    for key in ("local_buckling_mode_shape", "distortional_buckling_mode_shape"):
        if key in result:
            result[key] = _compose_deformed_shape(result[key])

    if is_inch:
        result["units"] = {"dimensions": "inch", "force": "kips", "stress": "ksi"}
    else:
        result["units"] = {"dimensions": "mm", "force": "N", "stress": "MPa"}

    return result


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
        # Register same tool on json server
        json_mcp.tool()(calculate_cee_buckling)
        app = json_mcp.streamable_http_app()
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        mcp.run(transport="streamable-http")
