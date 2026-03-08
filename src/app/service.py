from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections import deque
from dataclasses import asdict
from datetime import datetime, timedelta

from fastapi import WebSocket

from app.clients import BybitClient, CoinGeckoClient
from app.config import DetectorConfig
from app.detector import PumpDetector
from app.models import PumpSignal

logger = logging.getLogger(__name__)


class PumpScannerService:
    def __init__(self, config: DetectorConfig) -> None:
        self.config = config
        self.bybit = BybitClient()
        self.coingecko = CoinGeckoClient()
        self.detector = PumpDetector(config)
        self.market_caps: dict[str, float] = {}
        self.last_market_caps_update: datetime | None = None
        self.signals: deque[PumpSignal] = deque(maxlen=200)
        self.clients: set[WebSocket] = set()
        self.loop_task: asyncio.Task | None = None
        self.running = False

    async def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.loop_task = asyncio.create_task(self._run_loop())
        logger.info("Pump scanner service started")

    async def stop(self) -> None:
        self.running = False
        if self.loop_task:
            self.loop_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.loop_task
        logger.info("Pump scanner service stopped")

    async def register(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.clients.add(websocket)
        await websocket.send_json(
            {"type": "bootstrap", "signals": [asdict(x) for x in self.signals]}
        )

    async def unregister(self, websocket: WebSocket) -> None:
        self.clients.discard(websocket)

    async def _run_loop(self) -> None:
        while self.running:
            try:
                await self._refresh_market_caps_if_needed()
                ticks = await self.bybit.get_linear_tickers()
                found = self.detector.ingest(ticks, self.market_caps)
                for signal in found:
                    self.signals.appendleft(signal)
                    logger.info("Signal: %s", signal)
                    await self._broadcast({"type": "signal", "payload": asdict(signal)})
            except Exception as exc:  # noqa: BLE001
                logger.exception("Scan loop error: %s", exc)
                await self._broadcast({"type": "error", "message": str(exc)})
            await asyncio.sleep(self.config.poll_interval_seconds)

    async def _refresh_market_caps_if_needed(self) -> None:
        needs_refresh = (
            self.last_market_caps_update is None
            or datetime.utcnow() - self.last_market_caps_update > timedelta(minutes=30)
        )
        if needs_refresh:
            logger.info("Refreshing market cap cache")
            self.market_caps = await self.coingecko.get_market_caps()
            self.last_market_caps_update = datetime.utcnow()
            logger.info("Market cap cache refreshed with %d symbols", len(self.market_caps))

    async def _broadcast(self, message: dict[str, object]) -> None:
        if not self.clients:
            return
        dead: list[WebSocket] = []
        for ws in self.clients:
            try:
                await ws.send_text(json.dumps(message, default=str))
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    def list_signals(self) -> list[dict[str, object]]:
        return [asdict(x) for x in self.signals]

    def health(self) -> dict[str, object]:
        return {
            "running": self.running,
            "connected_clients": len(self.clients),
            "signals_cached": len(self.signals),
            "last_market_caps_update": self.last_market_caps_update.isoformat()
            if self.last_market_caps_update
            else None,
            "detector_state": self.detector.snapshot_state(),
        }
