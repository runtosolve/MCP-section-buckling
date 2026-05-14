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


class SvgBounds(BaseModel):
    """Machine-readable bounds for the SVG geometry.

    All fields describe the *union* of the three polylines (undeformed, local,
    distortional) — they share a single coordinate space, viewBox, and origin.
    The origin (0, 0) is the center of that union's bounding box. It is NOT
    the section centroid; the deformed mode shapes extend asymmetrically
    beyond the undeformed centerline, so the union center is shifted slightly
    from the section centroid.

    Use `width`/`height` to compute a fit-to-target scale without parsing the
    viewBox string. Use `content_width`/`content_height` if you want to fit
    the polylines themselves (no padding) into a tile.
    """

    width: float = Field(
        description="viewBox width, including padding. Equals 2*max(|x|) over the union of all polylines, plus padding."
    )
    height: float = Field(
        description="viewBox height, including padding."
    )
    xmin: float = Field(
        description="viewBox xmin (negative; the geometry is centered on the origin)."
    )
    ymin: float = Field(
        description="viewBox ymin (negative)."
    )
    content_width: float = Field(
        description="Tight bounding-box width of the polylines, without padding."
    )
    content_height: float = Field(
        description="Tight bounding-box height of the polylines, without padding."
    )
    origin: Literal["viewbox-center"] = Field(
        default="viewbox-center",
        description="Where (0, 0) sits. 'viewbox-center' = center of the union bounding box of all three polylines. Not the section centroid.",
    )


class SvgGeometry(BaseModel):
    viewBox: str = Field(
        description="SVG viewBox attribute string ('xmin ymin width height') sized to fit all shapes with padding. Use this verbatim on the <svg> element."
    )
    bounds: SvgBounds = Field(
        description="Numeric bounds and origin for the geometry. Use these instead of parsing the viewBox string when embedding into a larger SVG."
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
    svg: SvgGeometry = Field(
        description="Precomputed SVG-ready geometry (Y-flipped, padded viewBox) for direct use in <svg>/<polyline>."
    )


class SectionProperties(BaseModel):
    A: float = Field(description="Cross-sectional area")
    xc: float = Field(description="X coordinate of the centroid")
    yc: float = Field(description="Y coordinate of the centroid")
    Ixx: float = Field(description="Moment of inertia of x-axis")
    Iyy: float = Field(description="Moment of inertia of y-axis")
    Ixy: float = Field(
        description="Product of inertia about the x- and y- axes")
    theta: float = Field(
        alias="θ",
        description="Principal axis rotation angle (radians) from the centroidal x-axis",
    )
    I1: float = Field(description="Major principal moment of inertia")
    I2: float = Field(description="Minor principal moment of inertia")
    J: float = Field(description="Saint-Venant torsion constant")
    xs: float = Field(description="X coordinate of the shear center")
    ys: float = Field(description="Y coordinate of the shear center")
    Cw: float = Field(description="Warping torsion constant")
    B1: float = Field(description="Monosymmetry parameter about the 1-axis")
    B2: float = Field(description="Monosymmetry parameter about the 2-axis")

    model_config = {"populate_by_name": True}


class CeeBucklingResult(BaseModel):
    Pcrl: float = Field(description="Critical local buckling load")
    Pcrd: float = Field(description="Critical distortional buckling load")
    shapes: ShapeVisualization = Field(
        description=(
            "Mode shape data. Use shapes.svg for ALL rendering — it contains "
            "precomputed, Y-flipped SVG polyline strings ready for direct use in <polyline>."
        )
    )
    section_properties: SectionProperties = Field(
        description="Section properties of the cross-section"
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
) -> tuple[str, list[str], SvgBounds]:
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
    bounds = SvgBounds(
        width=round(vb_w, precision),
        height=round(vb_h, precision),
        xmin=round(vb_xmin, precision),
        ymin=round(vb_ymin, precision),
        content_width=round(2 * half_w, precision),
        content_height=round(2 * half_h, precision),
    )
    return view_box, points, bounds


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

    view_box, (und_pts, loc_pts, dist_pts), bounds = _build_svg_geometry([
        (undeformed_X, undeformed_Y),
        (local_X, local_Y),
        (distortional_X, distortional_Y),
    ])

    return ShapeVisualization(
        svg=SvgGeometry(
            viewBox=view_box,
            bounds=bounds,
            undeformed_points=und_pts,
            local_buckling_points=loc_pts,
            distortional_buckling_points=dist_pts,
        ),
    )


OVERALL_DESCRIPTION = """\
Calculate elastic buckling loads and section properties for a cold-formed C-section (Cee section) using finite-strip analysis.
Returns critical loads and SVG-ready mode shape geometry.

When using this tool, do not immediately return all the results to the user. In particular, do not immediately display the mode shapes, as they can be complex and may not be of interest to all users. 
Instead, first present exactly what the users asked for (critical loads or section properties) in a clear and concise manner.
Explain what you did, and then offer other results as optional follow-ups.
"""

SVG_RENDERING_INSTRUCTIONS = """\
## Rendering mode shapes

ALWAYS render mode shapes using `shapes.svg`. The server has already handled
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
whole section. Use `shapes.svg.bounds` to compute the scale without parsing
the viewBox string:

    s = target_height / shapes.svg.bounds.height
    <g transform="translate(cx, cy) scale(s)">
      <polyline points="{shapes.svg.undeformed_points}" .../>
      <polyline points="{shapes.svg.local_buckling_points}" .../>
    </g>

The composite figure is centered at (0, 0) — that is, the center of the union
bounding box of all three polylines, NOT the section centroid. So
`translate(cx, cy)` places that center at `(cx, cy)` with no offset math.
Use `shapes.svg.bounds.content_width`/`content_height` if you want to fit the
polylines themselves (no padding) into a tile.

### Placing legends, labels, and annotations

The polylines occupy nearly the full viewBox — a C-section spans the entire
height and most of the width. Do NOT place legends, titles, or labels inside
the viewBox on top of the geometry; they will collide with the section walls.

If you want a legend or labels:

1. **Extend the viewBox** to add a gutter beside the section, e.g. widen
   `width` by ~40% and shift `xmin` so the new space sits to the right (or
   below) the polylines. Place legend swatches and text in that gutter.
2. **Or render the legend in surrounding HTML/markup**, outside the `<svg>`.

Do NOT use an SVG `<mask>` to "punch text gaps" through the mode-shape
polylines. A mask that hides the polyline wherever a label sits will erase
real geometry (typically the top flange and lip, which live near y = ymin)
and make the mode shape look truncated. If you need text over a curve for
readability, draw the text with a contrasting `stroke`/`paint-order`, or
move the text out of the geometry region entirely.
"""


def _extract_section_properties(result: dict) -> SectionProperties:
    """Extract section properties from the result for reference."""
    return SectionProperties(
        A=result["section_properties"]["A"],
        xc=result["section_properties"]["xc"],
        yc=result["section_properties"]["yc"],
        Ixx=result["section_properties"]["Ixx"],
        Iyy=result["section_properties"]["Iyy"],
        Ixy=result["section_properties"]["Ixy"],
        θ=result["section_properties"]["θ"],
        I1=result["section_properties"]["I1"],
        I2=result["section_properties"]["I2"],
        J=result["section_properties"]["J"],
        xs=result["section_properties"]["xs"],
        ys=result["section_properties"]["ys"],
        Cw=result["section_properties"]["Cw"],
        B1=result["section_properties"]["B1"],
        B2=result["section_properties"]["B2"],
    )


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
        Field(description="Inside corner radius. Default: 0.0625 inch or 2.0 mm"),
    ] = None,
    E: Annotated[
        float | None,
        Field(description="Young's modulus. Default: 29500 ksi or 203000 MPa"),
    ] = None,
    nu: Annotated[float, Field(description="Poisson's ratio")] = 0.3,
    mode_shape_element_discretization: Annotated[int, Field(
        description="Number of finite strip elements per plate segment for mode shape calculation. Higher values yield smoother mode shapes at the cost of increased computation time. Default: 2")] = 2,
    units: Annotated[
        Literal["inch", "mm"],
        Field(description="Unit system — 'inch' (imperial) or 'mm' (metric). Default: 'inch'. Use imperial unless asked to do otherwise."),
    ] = "inch",
) -> CeeBucklingResult:
    """Calculate Cee section buckling loads and mode shapes."""
    is_inch = units.lower().startswith("in")
    if r is None:
        r = R_DEFAULT_IMPERIAL if is_inch else R_DEFAULT_METRIC
    if E is None:
        E = E_IMPERIAL if is_inch else E_METRIC

    payload = {"H": H, "B": B, "t": t, "L": L, "r": r, "E": E, "nu": nu,
               "mode_shape_element_discretization": mode_shape_element_discretization}
    with httpx.Client() as client:
        resp = client.post(f"{CEE_BACKEND_URL}/calculate",
                           json=payload, timeout=120)
        resp.raise_for_status()
        result = resp.json()

    return CeeBucklingResult(
        Pcrl=result["Pcrl"],
        Pcrd=result["Pcrd"],
        shapes=_create_shape_coordinates(result),
        section_properties=_extract_section_properties(result),
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
