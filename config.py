"""Process-wide configuration: backend URL, units, material defaults, SVG sizing."""

import os

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
