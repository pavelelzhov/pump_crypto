from datetime import datetime, timedelta

import pytest

from app.config import DEFAULT_ALERT_CONFIG, DEFAULT_CONFIG
from app.service import PumpScannerService


@pytest.mark.asyncio
async def test_market_cap_refresh_backoff_uses_cached_data() -> None:
    service = PumpScannerService(DEFAULT_CONFIG, DEFAULT_ALERT_CONFIG)
    service.market_caps = {"TEST": 123.0}

    async def fail_market_caps() -> dict[str, float]:
        raise RuntimeError("429 Too Many Requests")

    service.coingecko.get_market_caps = fail_market_caps  # type: ignore[method-assign]

    await service._refresh_market_caps_if_needed()

    assert service.market_caps == {"TEST": 123.0}
    assert service.market_caps_failures == 1
    assert service.market_caps_retry_after is not None
    assert service.last_market_caps_error == "429 Too Many Requests"


@pytest.mark.asyncio
async def test_market_cap_retry_window_skips_refresh() -> None:
    service = PumpScannerService(DEFAULT_CONFIG, DEFAULT_ALERT_CONFIG)
    service.market_caps = {"TEST": 123.0}
    service.market_caps_retry_after = datetime.utcnow() + timedelta(seconds=60)

    called = False

    async def should_not_run() -> dict[str, float]:
        nonlocal called
        called = True
        return {"NEW": 999.0}

    service.coingecko.get_market_caps = should_not_run  # type: ignore[method-assign]

    await service._refresh_market_caps_if_needed()

    assert called is False
    assert service.market_caps == {"TEST": 123.0}


def test_health_contains_market_cap_retry_metadata() -> None:
    service = PumpScannerService(DEFAULT_CONFIG, DEFAULT_ALERT_CONFIG)
    health = service.health()

    assert "market_caps_retry_after" in health
    assert "market_caps_failures" in health
    assert "last_market_caps_error" in health
