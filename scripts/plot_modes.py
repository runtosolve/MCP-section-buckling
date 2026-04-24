"""Plot the mode shapes correctly using X + ΔX · scale, Y + ΔY · scale.

Without the displacement, local and distortional modes look identical
(they share the same undeformed cross-section). The real difference is
in ΔX, ΔY — the eigenvector of the buckling mode.
"""

import json
import pathlib

import matplotlib.pyplot as plt

here = pathlib.Path(__file__).parent
data = json.loads((here / "mode_shapes.json").read_text())

Pcrl = data["Pcrℓ"]
Pcrd = data["Pcrd"]
local_ms = data["local_buckling_mode_shape"]
dist_ms = data["distortional_buckling_mode_shape"]

SCALE = 0.5  # amplify buckling displacement for visualization

fig, axes = plt.subplots(1, 2, figsize=(10, 6))

for ax, ms, title, load in [
    (axes[0], local_ms, "Local buckling", Pcrl),
    (axes[1], dist_ms, "Distortional buckling", Pcrd),
]:
    X = ms["X"]
    Y = ms["Y"]
    dX = ms["\u0394X"]
    dY = ms["\u0394Y"]
    x_def = [xi + dxi * SCALE for xi, dxi in zip(X, dX)]
    y_def = [yi + dyi * SCALE for yi, dyi in zip(Y, dY)]
    ax.plot(X, Y, "-", color="lightgray", linewidth=1.2, label="undeformed")
    ax.plot(x_def, y_def, "-", color="C0", linewidth=1.4, label=f"buckled (x{SCALE})")
    ax.set_aspect("equal")
    ax.set_title(f"{title}\nPcr = {load:.3f}")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="center", fontsize=8)

fig.tight_layout()

out = here / "modes.png"
fig.savefig(out, dpi=110, bbox_inches="tight")
print(f"Saved plot to {out}")
