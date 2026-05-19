import math

import httpx
import pytest

from config import CEE_BACKEND_URL
from tools.open_section.schema import Coordinates
from tools.open_section.tool import calculate_open_section_buckling


def test_calculate_open_section_buckling_live_backend():
    try:
        httpx.get(f"{CEE_BACKEND_URL}/", timeout=2.0)
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
        pytest.skip(f"Julia backend not reachable at {CEE_BACKEND_URL}")

    coordinates = Coordinates(
        X=[
            -0.2, 0.0, 0.0, -0.8, -1.0, -1.2, -2.0, -2.0, -1.8, -2.0, -2.0,
            -1.7, -1.7, -2.0, -2.0, -1.8, -2.0, -2.0, -1.2, -1.0, -0.8, 0.0,
            0.0, -0.2,
        ],
        Y=[
            -2.5, -2.5, -3.0, -3.0, -2.8, -3.0, -3.0, -1.7, -1.5, -1.3,
            -0.703731, -0.3, 0.3, 0.696264, 1.3, 1.5, 1.7, 3.0, 3.0, 2.8,
            3.0, 3.0, 2.5, 2.5,
        ],
    )

    result = calculate_open_section_buckling(
        coordinates=coordinates,
        t=0.054,
        units="inch",
    )

    assert result.Rcrl is not None
    assert result.Rcrd is not None
    assert isinstance(result.Rcrl, float) and isinstance(result.Rcrd, float)
    assert math.isfinite(result.Rcrl) and math.isfinite(result.Rcrd)
    assert result.Rcrl > 0 and result.Rcrd > 0
