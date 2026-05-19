import math

import httpx
import pytest

from config import CEE_BACKEND_URL
from tools.cee_section.tool import calculate_cee_buckling


def test_calculate_cee_buckling_live_backend():
    try:
        httpx.get(f"{CEE_BACKEND_URL}/", timeout=2.0)
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
        pytest.skip(f"Julia backend not reachable at {CEE_BACKEND_URL}")

    result = calculate_cee_buckling(H=8, B=2.5, L=0.625, t=0.054, units="inch")

    assert result.Pcrl is not None
    assert result.Pcrd is not None
    assert isinstance(result.Pcrl, float) and isinstance(result.Pcrd, float)
    assert math.isfinite(result.Pcrl) and math.isfinite(result.Pcrd)
    assert result.Pcrl > 0 and result.Pcrd > 0
