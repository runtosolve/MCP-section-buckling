import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx
import math

from config import CEE_BACKEND_URL

payload = {
    "E": 29500.0,
    "nu": 0.30,
    "t": 0.102,
    "coordinates": {
        "X": [0.0, 1.0, 2.0, 3.0, 4.0],
        "Y": [0.0, 2.0, 6.0, 8.0, 3.0],
    },
    "centerline_radius": 2 * 0.102,
    "loads": {"P": 1.0, "Mxx": 0.0, "Mzz": 0.0, "M11": 0.0, "M22": 0.0},
    "load_type": "P",
    "flat_mesh_size_goal": 0.5,
    "corner_mesh_size_goal": math.pi / 6,
    "mode_shape_element_discretization": 2,
}

OUT_DIR = os.path.dirname(__file__)


def main() -> None:
    url = f"{CEE_BACKEND_URL}/calculate_open_section"
    print(f"POST {url}")
    with httpx.Client() as client:
        resp = client.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        result = resp.json()

    out_path = os.path.join(OUT_DIR, "open_section_response.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"OK — wrote {out_path}")
    print(
        f"  local: label={result.get('local_buckling_label')}  "
        f"Lcrl={result.get('Lcrl')}  Rcrl={result.get('Rcrl')}"
    )
    print(
        f"  distortional: label={result.get('distortional_buckling_label')}  "
        f"Lcrd={result.get('Lcrd')}  Rcrd={result.get('Rcrd')}"
    )


if __name__ == "__main__":
    main()
