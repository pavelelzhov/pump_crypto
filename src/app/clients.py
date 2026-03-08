from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.models import TickSnapshot


class BybitClient:
    def __init__(self, base_url: str = "https://api.bybit.com") -> None:
        self.base_url = base_url

    async def get_linear_tickers(self) -> list[TickSnapshot]:
        url = f"{self.base_url}/v5/market/tickers"
        params = {"category": "linear"}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
        payload = response.json()
        rows = payload.get("result", {}).get("list", [])
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        snapshots: list[TickSnapshot] = []
        for row in rows:
            symbol = row.get("symbol", "")
            if not symbol.endswith("USDT"):
                continue
            try:
                snapshots.append(
                    TickSnapshot(
                        symbol=symbol,
                        price=float(row.get("lastPrice", 0)),
                        volume_24h=float(row.get("turnover24h", 0)),
                        ts=now,
                    )
                )
            except (TypeError, ValueError):
                continue
        return snapshots

    async def get_klines(
        self, symbol: str, interval: str = "1", limit: int = 200, category: str = "linear"
    ) -> list[dict[str, Any]]:
        url = f"{self.base_url}/v5/market/kline"
        params = {
            "category": category,
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
        return response.json().get("result", {}).get("list", [])


class CoinGeckoClient:
    def __init__(self, base_url: str = "https://api.coingecko.com/api/v3") -> None:
        self.base_url = base_url

    async def get_market_caps(self, page_size: int = 250, pages: int = 3) -> dict[str, float]:
        cap_map: dict[str, float] = {}
        async with httpx.AsyncClient(timeout=30) as client:
            for page in range(1, pages + 1):
                url = f"{self.base_url}/coins/markets"
                params = {
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": page_size,
                    "page": page,
                    "sparkline": "false",
                }
                response = await client.get(url, params=params)
                response.raise_for_status()
                for row in response.json():
                    symbol = str(row.get("symbol", "")).upper()
                    cap = row.get("market_cap")
                    if symbol and isinstance(cap, (int, float)):
                        cap_map[symbol] = float(cap)
        return cap_map
