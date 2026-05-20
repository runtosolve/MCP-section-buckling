"""calculate_open_section_buckling MCP tool — finite-strip buckling for an arbitrary open thin-walled section."""

import math
from typing import Annotated, Literal

from pydantic import Field

from config import E_IMPERIAL, E_METRIC, IMPERIAL_UNITS, METRIC_UNITS
from tools.shared.backend import call_backend
from tools.shared.shapes import (
    SVG_RENDERING_INSTRUCTIONS,
    create_shape_visualization,
    extract_section_properties,
)

from .schema import Coordinates, OpenSectionBucklingResult

ENDPOINT = "/calculate_open_section"

OVERALL_DESCRIPTION = """\
Calculate elastic buckling loads/moments for an arbitrary open thin-walled cold-formed section
defined by a centerline polyline, using finite-strip analysis. Returns section properties,
critical local and distortional buckling magnitudes (with descriptive labels), associated
half-wavelengths, and mode shapes as SVG-ready coordinates.

The section is defined by `coordinates` (the X, Y polyline along the wall centerline) and a
uniform thickness `t`. Bends are inserted at each interior node with `centerline_radius`.
`load_type` selects the single load case driving the buckling analysis ('P' for compression,
'Mxx'/'Mzz' for bending about centroidal axes, 'M11'/'M22' for bending about principal axes);
the buckling magnitude is reported as a multiplier on a unit load of that type.

When using this tool, only return the results requested by the user.
Do not provide interpretation of the results unless explicitly requested.
Do not immediately render the SVG mode shapes unless requested because the user may not be interested in them.
Provide the SVG geometry only when requested.
"""


def calculate_open_section_buckling(
    coordinates: Annotated[
        Coordinates,
        Field(description="Centerline polyline of the open section as parallel X and Y arrays"),
    ],
    t: Annotated[float, Field(description="Wall thickness (uniform)")],
    load_type: Annotated[
        Literal["P", "Mxx", "Mzz", "M11", "M22"],
        Field(description="Which load case drives the buckling analysis"),
    ] = "P",
    centerline_radius: Annotated[
        float | None,
        Field(description="Inside corner centerline radius at each interior node. Default: 2*t"),
    ] = None,
    E: Annotated[
        float | None,
        Field(description="Young's modulus. Default: 203000 MPa or 29500 ksi"),
    ] = None,
    nu: Annotated[float, Field(description="Poisson's ratio")] = 0.3,
    flat_mesh_size_goal: Annotated[
        float,
        Field(description="Target finite-strip element size along flat segments"),
    ] = 0.5,
    corner_mesh_size_goal: Annotated[
        float,
        Field(description="Target finite-strip element angular size along corner arcs (radians). Default: π/6"),
    ] = math.pi / 6,
    mode_shape_element_discretization: Annotated[
        int,
        Field(
            description=(
                "Number of finite strip elements per plate segment for mode shape calculation. "
                "Higher values yield smoother mode shapes at the cost of increased computation time. Default: 2"
            )
        ),
    ] = 2,
    units: Annotated[
        Literal["mm", "inch"],
        Field(description="Unit system — 'mm' (metric) or 'inch' (imperial)"),
    ] = "mm",
) -> OpenSectionBucklingResult:
    """Calculate open thin-walled section buckling loads and mode shapes."""
    is_inch = units.lower().startswith("in")
    if E is None:
        E = E_IMPERIAL if is_inch else E_METRIC
    if centerline_radius is None:
        centerline_radius = 2 * t

    loads = {k: (1.0 if k == load_type else 0.0) for k in ("P", "Mxx", "Mzz", "M11", "M22")}

    payload = {
        "E": E,
        "nu": nu,
        "t": t,
        "coordinates": {"X": coordinates.X, "Y": coordinates.Y},
        "centerline_radius": centerline_radius,
        "loads": loads,
        "load_type": load_type,
        "flat_mesh_size_goal": flat_mesh_size_goal,
        "corner_mesh_size_goal": corner_mesh_size_goal,
        "mode_shape_element_discretization": mode_shape_element_discretization,
    }
    result = call_backend(ENDPOINT, payload)

    units_dict = IMPERIAL_UNITS if is_inch else METRIC_UNITS
    return OpenSectionBucklingResult(
        local_buckling_label=result["local_buckling_label"],
        distortional_buckling_label=result["distortional_buckling_label"],
        Lcrl=result["Lcrl"],
        Lcrd=result["Lcrd"],
        Rcrl=result["Rcrl"],
        Rcrd=result["Rcrd"],
        shapes=create_shape_visualization(
            result, result["Rcrl"], result["Rcrd"], units_dict,
            Pcrl_label="Rcrl", Pcrd_label="Rcrd",
        ),
        section_properties=extract_section_properties(result),
        units=units_dict,
    )


def register(mcp) -> None:
    mcp.tool(
        name="calculate_open_section_buckling",
        description="\n".join([OVERALL_DESCRIPTION, SVG_RENDERING_INSTRUCTIONS]),
    )(calculate_open_section_buckling)
