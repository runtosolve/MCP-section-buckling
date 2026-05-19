"""Result schema for the calculate_cee_buckling tool."""

from pydantic import BaseModel, Field

from tools.shared.schemas import SectionProperties, ShapeVisualization


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
