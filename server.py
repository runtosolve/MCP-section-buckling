"""CEE Section Buckling — Remote MCP Server (Streamable HTTP)."""

import os
from typing import Annotated, Literal

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, Field
from starlette.requests import Request
from starlette.responses import Response

CEE_BACKEND_URL = os.environ.get("CEE_BACKEND_URL", "http://localhost:8081")

# Raw eigenvector displacements are normalized so max|Δ| maps to this
# fraction of the section's smaller span. Large enough to show the
# buckling shape, small enough not to distort the section outline.
MODE_SHAPE_VISUALIZATION_RATIO = 0.15

SVG_TARGET_HEIGHT = 400.0

IMPERIAL_UNITS = {"dimensions": "inch", "force": "kips", "stress": "ksi"}
METRIC_UNITS = {"dimensions": "mm", "force": "N", "stress": "MPa"}
E_IMPERIAL = 29500.0  # ksi
E_METRIC = 203000.0  # MPa
R_DEFAULT_IMPERIAL = 0.0625  # inch
R_DEFAULT_METRIC = 2.0  # mm


class ModeShapeCoordinates(BaseModel):
    X: list[float] = Field(
        description="X coordinates of the shape in engineering units"
    )
    Y: list[float] = Field(
        description="Y coordinates of the shape in engineering units"
    )


class SvgGeometry(BaseModel):
    viewBox: str = Field(
        description="SVG viewBox attribute string ('xmin ymin width height') sized to fit all shapes with padding. Use this verbatim on the <svg> element."
    )
    undeformed_points: str = Field(
        description="Space-separated 'x,y x,y …' polyline points for the undeformed centerline, with Y already flipped for SVG. Drop into <polyline points=\"…\"/>."
    )
    local_buckling_points: str = Field(
        description="Polyline points for the local buckling deformed shape, in the same SVG coordinate space as viewBox/undeformed_points."
    )
    distortional_buckling_points: str = Field(
        description="Polyline points for the distortional buckling deformed shape, in the same SVG coordinate space as viewBox/undeformed_points."
    )


class ShapeVisualization(BaseModel):
    undeformed: ModeShapeCoordinates = Field(
        description="Undeformed wall centerline coordinates in engineering units"
    )
    local_buckling: ModeShapeCoordinates = Field(
        description="Local buckling mode shape coordinates in engineering units (deformed)"
    )
    distortional_buckling: ModeShapeCoordinates = Field(
        description="Distortional buckling mode shape coordinates in engineering units (deformed)"
    )
    svg: SvgGeometry = Field(
        description="Precomputed SVG-ready geometry (Y-flipped, padded viewBox) for direct use in <svg>/<polyline>. Use this when rendering SVG instead of remapping the engineering coordinates yourself."
    )


class CeeBucklingResult(BaseModel):
    Pcrl: float = Field(description="Critical local buckling load")
    Pcrd: float = Field(description="Critical distortional buckling load")
    shapes: ShapeVisualization = Field(
        description=(
            "Mode shape data. Use shapes.svg for ALL rendering — it contains "
            "precomputed, Y-flipped SVG polyline strings ready for direct use in <polyline>. "
            "The raw X/Y coordinate arrays (shapes.undeformed, shapes.local_buckling, "
            "shapes.distortional_buckling) are for numerical reference only; "
            "do NOT use them to render or reconstruct the mode shapes."
        )
    )
    units: dict = Field(
        description="Units for dimensions, force, and stress (e.g., {'dimensions': 'mm', 'force': 'N', 'stress': 'MPa'})"
    )


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


def _round_coordinates(coords: list[float], precision: int = 4) -> list[float]:
    """Round coordinates to specified decimal places for token efficiency."""
    return [round(coord, precision) for coord in coords]


def _build_svg_geometry(
    curves: list[tuple[list[float], list[float]]],
    padding_ratio: float = 0.05,
    precision: int = 2,
) -> tuple[str, list[str]]:
    """Build a shared SVG viewBox and Y-flipped polyline point strings.

    Coordinates are uniformly scaled so the Y span maps to ~SVG_TARGET_HEIGHT
    units (aspect ratio preserved). The bounding box is centered at the SVG
    origin (0, 0), so the viewBox is symmetric and transforms such as rotation
    or scaling need no additional translation offset. SVG's Y axis grows
    downward, so we negate Y before centering.
    """
    all_x = [x for xs, _ in curves for x in xs]
    all_y = [y for _, ys in curves for y in ys]
    xmin, xmax = min(all_x), max(all_x)
    ymin, ymax = min(all_y), max(all_y)
    y_span = ymax - ymin
    scale = SVG_TARGET_HEIGHT / y_span if y_span > 0 else 1.0

    # Center of the bounding box in SVG space (Y-flipped).
    cx = (xmin + xmax) / 2 * scale
    cy = -(ymin + ymax) / 2 * scale

    pad = padding_ratio * max((xmax - xmin) * scale, y_span * scale)
    half_w = (xmax - xmin) / 2 * scale
    half_h = y_span / 2 * scale
    vb_xmin = -half_w - pad
    vb_ymin = -half_h - pad
    vb_w = 2 * half_w + 2 * pad
    vb_h = 2 * half_h + 2 * pad
    view_box = (
        f"{round(vb_xmin, precision)} {round(vb_ymin, precision)} "
        f"{round(vb_w, precision)} {round(vb_h, precision)}"
    )

    points = [
        " ".join(
            f"{round(x * scale - cx, precision)},{round(-y * scale - cy, precision)}"
            for x, y in zip(xs, ys)
        )
        for xs, ys in curves
    ]
    return view_box, points


def _create_shape_coordinates(result: dict) -> ShapeVisualization:
    """Create shape coordinate data for visualization in engineering units."""
    # Undeformed coordinates come from the distortional mode base because it
    # covers the full section perimeter; the local mode only spans the
    # sub-segment (flange + lip) relevant to that mode.
    distortional_mode = result["distortional_buckling_mode_shape"]
    undeformed_X = _round_coordinates(distortional_mode["X"])
    undeformed_Y = _round_coordinates(distortional_mode["Y"])

    # Local buckling mode shape
    local_coords = _compose_deformed_shape(result["local_buckling_mode_shape"])
    local_X = _round_coordinates(local_coords["X"])
    local_Y = _round_coordinates(local_coords["Y"])

    # Distortional buckling mode shape
    distortional_coords = _compose_deformed_shape(
        result["distortional_buckling_mode_shape"])
    distortional_X = _round_coordinates(distortional_coords["X"])
    distortional_Y = _round_coordinates(distortional_coords["Y"])

    view_box, (und_pts, loc_pts, dist_pts) = _build_svg_geometry([
        (undeformed_X, undeformed_Y),
        (local_X, local_Y),
        (distortional_X, distortional_Y),
    ])

    return ShapeVisualization(
        undeformed=ModeShapeCoordinates(X=undeformed_X, Y=undeformed_Y),
        local_buckling=ModeShapeCoordinates(X=local_X, Y=local_Y),
        distortional_buckling=ModeShapeCoordinates(
            X=distortional_X, Y=distortional_Y),
        svg=SvgGeometry(
            viewBox=view_box,
            undeformed_points=und_pts,
            local_buckling_points=loc_pts,
            distortional_buckling_points=dist_pts,
        ),
    )


OVERALL_DESCRIPTION = """\
Calculate elastic buckling loads for a cold-formed C-section (Cee section) using finite-strip analysis.
Returns critical loads and SVG-ready mode shape geometry.
"""

SVG_RENDERING_INSTRUCTIONS = """\
## Rendering mode shapes

ALWAYS render mode shapes using `shapes.svg`. Never manually remap or
reinterpret the raw engineering coordinates — the server has already handled
the Y-axis flip, uniform scaling, padding, and centering.

### Minimal standalone SVG (auto-fits the section)

    <svg xmlns="http://www.w3.org/2000/svg" viewBox="{shapes.svg.viewBox}">
      <!-- undeformed centerline -->
      <polyline points="{shapes.svg.undeformed_points}"
                fill="none" stroke="#888" stroke-dasharray="2,2"
                vector-effect="non-scaling-stroke"/>
      <!-- local buckling mode shape -->
      <polyline points="{shapes.svg.local_buckling_points}"
                fill="none" stroke="#1f77b4"
                vector-effect="non-scaling-stroke"/>
      <!-- distortional buckling mode shape -->
      <polyline points="{shapes.svg.distortional_buckling_points}"
                fill="none" stroke="#d62728"
                vector-effect="non-scaling-stroke"/>
    </svg>

Set `viewBox="{shapes.svg.viewBox}"` on the `<svg>` element when you want the
SVG to auto-frame the section. All three point strings share the same coordinate
space so they can be overlaid freely. Use `vector-effect="non-scaling-stroke"`
so stroke widths stay crisp at any scale.

### Embedding inside a larger SVG

Place the polylines in a `<g>` and apply a single `transform` to position the
whole section:

    <g transform="translate(cx, cy) scale(s)">
      <polyline points="{shapes.svg.undeformed_points}" .../>
      <polyline points="{shapes.svg.local_buckling_points}" .../>
    </g>

The geometry is centered at (0, 0) so scaling or rotating needs no extra
translation offset.

## Matplotlib (only when the user explicitly asks for matplotlib)

    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 6))
    for ax, coords, title, load in [
        (axes[0], result.shapes.local_buckling, "Local", result.Pcrl),
        (axes[1], result.shapes.distortional_buckling, "Distortional", result.Pcrd),
    ]:
        ax.plot(coords.X, coords.Y, "-")
        ax.set_aspect("equal")
        ax.set_title(f"{title} buckling\\nPcr = {load:.3f}")

Do NOT rescale, slice, or reinterpret the coordinates — just plot X vs Y.
"""


@mcp.tool(
    name="calculate_cee_buckling",
    description="\n".join([OVERALL_DESCRIPTION, SVG_RENDERING_INSTRUCTIONS]),
)
def calculate_cee_buckling(
    H: Annotated[float, Field(description="Web height")],
    B: Annotated[float, Field(description="Flange width")],
    t: Annotated[float, Field(description="Thickness")],
    L: Annotated[float, Field(description="Lip width")],
    r: Annotated[
        float | None,
        Field(description="Inside corner radius. Default: 2.0 mm or 0.0625 inch"),
    ] = None,
    E: Annotated[
        float | None,
        Field(description="Young's modulus. Default: 203000 MPa or 29500 ksi"),
    ] = None,
    nu: Annotated[float, Field(description="Poisson's ratio")] = 0.3,
    units: Annotated[
        Literal["mm", "inch"],
        Field(description="Unit system — 'mm' (metric) or 'inch' (imperial)"),
    ] = "mm",
) -> CeeBucklingResult:
    """Calculate Cee section buckling loads and mode shapes."""
    is_inch = units.lower().startswith("in")
    if r is None:
        r = R_DEFAULT_IMPERIAL if is_inch else R_DEFAULT_METRIC
    if E is None:
        E = E_IMPERIAL if is_inch else E_METRIC

    payload = {"H": H, "B": B, "t": t, "L": L, "r": r, "E": E, "nu": nu}
    with httpx.Client() as client:
        resp = client.post(f"{CEE_BACKEND_URL}/calculate",
                           json=payload, timeout=120)
        resp.raise_for_status()
        result = resp.json()

    return CeeBucklingResult(
        Pcrl=result["Pcrl"],
        Pcrd=result["Pcrd"],
        shapes=_create_shape_coordinates(result),
        units=IMPERIAL_UNITS if is_inch else METRIC_UNITS,
    )


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
