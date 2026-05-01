"""Call the CEE buckling backend and write the resulting SVG to this folder."""

from server import (
    CEE_BACKEND_URL,
    E_IMPERIAL,
    R_DEFAULT_IMPERIAL,
    _create_shape_coordinates,
)
import httpx
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


INPUT = {"H": 3.5, "B": 2, "L": 0.5, "t": 0.054,
         "r": R_DEFAULT_IMPERIAL, "E": E_IMPERIAL, "nu": 0.3}
OUT_DIR = os.path.dirname(__file__)


def main() -> None:
    print(f"POST {CEE_BACKEND_URL}/calculate  input={INPUT}")
    with httpx.Client() as client:
        resp = client.post(f"{CEE_BACKEND_URL}/calculate",
                           json=INPUT, timeout=120)
        resp.raise_for_status()
        result = resp.json()

    with open(os.path.join(OUT_DIR, "result.json"), "w") as f:
        import json
        json.dump(result, f, indent=2)

    print(f"Pcrl={result['Pcrl']:.4f} kips   Pcrd={result['Pcrd']:.4f} kips")

    shapes = _create_shape_coordinates(result)
    svg = shapes.svg

    for name, pts_str, stroke, dash in [
        ("undeformed",      svg.undeformed_points,
         "#888888", 'stroke-dasharray="4,4"'),
        ("local",           svg.local_buckling_points,        "#1f77b4", ""),
        ("distortional",    svg.distortional_buckling_points, "#d62728", ""),
    ]:
        path = os.path.join(OUT_DIR, f"result_{name}.svg")
        svg_text = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{svg.viewBox}">\n'
            f'  <polyline points="{pts_str}"\n'
            f'            fill="none" stroke="{stroke}" stroke-width="2" {dash}\n'
            f'            vector-effect="non-scaling-stroke"/>\n'
            f'</svg>\n'
        )
        with open(path, "w") as f:
            f.write(svg_text)
        n = len(pts_str.split())
        print(f"  wrote {path}  ({n} points, viewBox={svg.viewBox})")

    # Combined SVG with all three shapes overlaid
    combined_path = os.path.join(OUT_DIR, "result_combined.svg")
    combined = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{svg.viewBox}">\n'
        f'  <polyline points="{svg.undeformed_points}"\n'
        f'            fill="none" stroke="#888888" stroke-width="2" stroke-dasharray="4,4"\n'
        f'            vector-effect="non-scaling-stroke"/>\n'
        f'  <polyline points="{svg.local_buckling_points}"\n'
        f'            fill="none" stroke="#1f77b4" stroke-width="2"\n'
        f'            vector-effect="non-scaling-stroke"/>\n'
        f'  <polyline points="{svg.distortional_buckling_points}"\n'
        f'            fill="none" stroke="#d62728" stroke-width="2"\n'
        f'            vector-effect="non-scaling-stroke"/>\n'
        f'</svg>\n'
    )
    with open(combined_path, "w") as f:
        f.write(combined)
    print(f"  wrote {combined_path}  (all three overlaid)")


if __name__ == "__main__":
    main()
