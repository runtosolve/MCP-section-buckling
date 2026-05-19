"""HTTP client for the Julia buckling backend and shared input default resolution."""

import httpx

from config import (
    CEE_BACKEND_URL,
    E_IMPERIAL,
    E_METRIC,
    R_DEFAULT_IMPERIAL,
    R_DEFAULT_METRIC,
)


def call_backend(endpoint: str, payload: dict, timeout: float = 120) -> dict:
    """POST `payload` to `endpoint` on the Julia backend and return parsed JSON."""
    with httpx.Client() as client:
        resp = client.post(f"{CEE_BACKEND_URL}{endpoint}", json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()


def resolve_material_defaults(
    r: float | None, E: float | None, units: str
) -> tuple[float, float, bool]:
    """Fill in `r` and `E` defaults based on the unit system.

    Returns `(r, E, is_inch)`.
    """
    is_inch = units.lower().startswith("in")
    if r is None:
        r = R_DEFAULT_IMPERIAL if is_inch else R_DEFAULT_METRIC
    if E is None:
        E = E_IMPERIAL if is_inch else E_METRIC
    return r, E, is_inch
