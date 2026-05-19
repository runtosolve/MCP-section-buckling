"""Shape post-processing: backend mode-shape dicts → SVG-ready geometry."""

from config import MODE_SHAPE_VISUALIZATION_RATIO, SVG_TARGET_HEIGHT

from .schemas import (
    SectionProperties,
    ShapeVisualization,
    SvgBounds,
    SvgGeometry,
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
    dX = mode_shape.get("ΔX")
    dY = mode_shape.get("ΔY")

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


def create_shape_visualization(result: dict) -> ShapeVisualization:
    """Create shape coordinate data for visualization in engineering units."""
    # Undeformed coordinates come from the distortional mode base because it
    # covers the full section perimeter; the local mode only spans the
    # sub-segment (flange + lip) relevant to that mode.
    distortional_mode = result["distortional_buckling_mode_shape"]
    undeformed_X = _round_coordinates(distortional_mode["X"])
    undeformed_Y = _round_coordinates(distortional_mode["Y"])

    local_coords = _compose_deformed_shape(result["local_buckling_mode_shape"])
    local_X = _round_coordinates(local_coords["X"])
    local_Y = _round_coordinates(local_coords["Y"])

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


def extract_section_properties(result: dict) -> SectionProperties:
    """Extract section properties from the backend result."""
    sp = result["section_properties"]
    return SectionProperties(
        A=sp["A"],
        xc=sp["xc"],
        yc=sp["yc"],
        Ixx=sp["Ixx"],
        Iyy=sp["Iyy"],
        Ixy=sp["Ixy"],
        θ=sp["θ"],
        I1=sp["I1"],
        I2=sp["I2"],
        J=sp["J"],
        xs=sp["xs"],
        ys=sp["ys"],
        Cw=sp["Cw"],
        B1=sp["B1"],
        B2=sp["B2"],
    )


SVG_RENDERING_INSTRUCTIONS = """\
## Rendering mode shapes

ALWAYS render mode shapes using `shapes.svg`. The server has already handled
the Y-axis flip, uniform scaling, padding, and centering.

Never put textbox, labels or legends over the SVG polylines because they may obscure the shapes.

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
"""
