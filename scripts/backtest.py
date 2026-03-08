"""Simple backtest for early pump detector using Bybit historical 1m kline data."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime

from app.clients import BybitClient
from app.config import DetectorConfig
from app.detector import PumpDetector
from app.models import TickSnapshot


async def run(symbol: str, limit: int) -> None:
    cfg = DetectorConfig(min_score=0.55, min_move_pct=3.0)
    detector = PumpDetector(cfg)
    client = BybitClient()
    klines = await client.get_klines(symbol=symbol, limit=limit)

    signals = 0
    for row in reversed(klines):
        ts_ms, _, _, _, close, turnover, *_ = row
        tick = TickSnapshot(
            symbol=symbol,
            price=float(close),
            volume_24h=float(turnover),
            open_interest=0.0,
            funding_rate=0.0,
            bid1_price=float(close),
            ask1_price=float(close),
            ts=datetime.utcfromtimestamp(int(ts_ms) / 1000),
        )
        found = detector.ingest([tick], {symbol.removesuffix('USDT'): 500_000_000})
        signals += len(found)

    print(f"Backtest symbol={symbol} candles={len(klines)} signals={signals}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="WIFUSDT")
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    asyncio.run(run(args.symbol, args.limit))
