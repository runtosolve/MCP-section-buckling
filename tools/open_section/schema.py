"""Input and result schemas for the calculate_open_section_buckling tool."""

from pydantic import BaseModel, Field

from tools.shared.schemas import SectionProperties, ShapeVisualization


class Coordinates(BaseModel):
    X: list[float] = Field(description="X coordinates of the section centerline nodes")
    Y: list[float] = Field(description="Y coordinates of the section centerline nodes")


class OpenSectionBucklingResult(BaseModel):
    local_buckling_label: str = Field(
        description="Label describing the critical local buckling quantity (e.g. 'Pcrl' or 'Mcrl')"
    )
    distortional_buckling_label: str = Field(
        description="Label describing the critical distortional buckling quantity"
    )
    Lcrl: float = Field(description="Critical local buckling half-wavelength")
    Lcrd: float = Field(description="Critical distortional buckling half-wavelength")
    Rcrl: float = Field(
        description="Critical local buckling load/moment magnitude (interpretation given by local_buckling_label)"
    )
    Rcrd: float = Field(
        description="Critical distortional buckling load/moment magnitude (interpretation given by distortional_buckling_label)"
    )
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
