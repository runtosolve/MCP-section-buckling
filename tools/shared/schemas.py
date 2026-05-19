"""Shared leaf schemas reused across tool result models."""

from typing import Literal

from pydantic import BaseModel, Field


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
