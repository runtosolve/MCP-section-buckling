"""calculate_cee_buckling MCP tool — finite-strip buckling for a Cee section."""

from typing import Annotated, Literal

from pydantic import Field

from tools.shared.backend import call_backend, resolve_material_defaults
from config import IMPERIAL_UNITS, METRIC_UNITS
from tools.shared.shapes import (
    SVG_RENDERING_INSTRUCTIONS,
    create_shape_visualization,
    extract_section_properties,
)

from .schema import CeeBucklingResult

ENDPOINT = "/calculate_cee_section"

OVERALL_DESCRIPTION = """\
Calculate elastic buckling loads for a cold-formed C-section (Cee section) using finite-strip analysis.
Returns section properties, critical local and distortional buckling loads, and mode shapes as SVG-ready coordinates.
When using this tool, only return the results requested by the user.
Do not provide interpretation of the results unless explicitly requested.
Do not immediately render the SVG mode shapes unless requested because the user may not be interested in them.
Provide the SVG geometry only when requested.
"""


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
    mode_shape_element_discretization: Annotated[int, Field(
        description="Number of finite strip elements per plate segment for mode shape calculation. Higher values yield smoother mode shapes at the cost of increased computation time. Default: 2")] = 2,
    units: Annotated[
        Literal["mm", "inch"],
        Field(description="Unit system — 'mm' (metric) or 'inch' (imperial)"),
    ] = "mm",
) -> CeeBucklingResult:
    """Calculate Cee section buckling loads and mode shapes."""
    r, E, is_inch = resolve_material_defaults(r, E, units)

    payload = {"H": H, "B": B, "t": t, "L": L, "r": r, "E": E, "nu": nu,
               "mode_shape_element_discretization": mode_shape_element_discretization}
    result = call_backend(ENDPOINT, payload)

    return CeeBucklingResult(
        Pcrl=result["Pcrl"],
        Pcrd=result["Pcrd"],
        shapes=create_shape_visualization(result),
        section_properties=extract_section_properties(result),
        units=IMPERIAL_UNITS if is_inch else METRIC_UNITS,
    )


def register(mcp) -> None:
    mcp.tool(
        name="calculate_cee_buckling",
        description="\n".join([OVERALL_DESCRIPTION, SVG_RENDERING_INSTRUCTIONS]),
    )(calculate_cee_buckling)
