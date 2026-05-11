
import sys
import os
from server import (
    CEE_BACKEND_URL,
)
import httpx
payload = {
    "H": 8,
    "B": 2.5,
    "L": 0.625,
    "t": 0.054,
    "units": "inch",
    "mode_shape_element_discretization": 2,
}

OUT_DIR = os.path.dirname(__file__)


def main() -> None:
    print(f"POST {CEE_BACKEND_URL}/calculate  input={payload}")
    with httpx.Client() as client:
        resp = client.post(f"{CEE_BACKEND_URL}/calculate",
                           json=payload, timeout=120)
        resp.raise_for_status()
        result = resp.json()

    with open(os.path.join(OUT_DIR, "result.json"), "w") as f:
        import json
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    main()
