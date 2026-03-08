from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections import Counter, deque
from dataclasses import asdict
from datetime import datetime, timedelta

from fastapi import WebSocket

from app.clients import BybitClient, CoinGeckoClient
from app.config import AlertConfig, DetectorConfig
from app.detector import PumpDetector
from app.models import PumpSignal
from app.notifiers import AlertDispatcher

logger = logging.getLogger(__name__)


class PumpScannerService:
    def __init__(self, config: DetectorConfig, alert_config: AlertConfig) -> None:
        self.config = config
        self.alert_config = alert_config
        self.bybit = BybitClient()
        self.coingecko = CoinGeckoClient()
        self.detector = PumpDetector(config)
        self.dispatcher = AlertDispatcher(alert_config)
        self.market_caps: dict[str, float] = {}
        self.last_market_caps_update: datetime | None = None
        self.signals: deque[PumpSignal] = deque(maxlen=400)
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
            {
                "type": "bootstrap",
                "signals": [asdict(x) for x in self.signals],
                "config": self.config.model_dump(),
                "alert_config": self.safe_alert_config(),
                "report": self.report(),
            }
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
                    await self.dispatcher.dispatch(signal)
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

    def update_config(self, values: dict[str, float | int | str]) -> DetectorConfig:
        self.config = self.config.model_copy(update=values)
        self.detector.config = self.config
        return self.config

    def update_alert_config(self, values: dict[str, object]) -> AlertConfig:
        self.alert_config = self.alert_config.model_copy(update=values)
        self.dispatcher.update_config(self.alert_config)
        return self.alert_config

    def safe_alert_config(self) -> dict[str, object]:
        data = self.alert_config.model_dump()
        data["telegram_bot_token_set"] = bool(data.get("telegram_bot_token"))
        data["telegram_chat_id_set"] = bool(data.get("telegram_chat_id"))
        data["webhook_url_set"] = bool(data.get("webhook_url"))
        data.pop("telegram_bot_token", None)
        data.pop("telegram_chat_id", None)
        data.pop("webhook_url", None)
        return data

    def report(self) -> dict[str, object]:
        day_ago = datetime.utcnow() - timedelta(hours=24)
        fresh = [s for s in self.signals if s.timestamp >= day_ago]
        if not fresh:
            return {
                "signals_24h": 0,
                "avg_score": 0,
                "avg_move_60s_pct": 0,
                "avg_final_score": 0,
                "top_symbols": [],
                "ml_scored_signals": 0,
            }
        counter = Counter(x.symbol for x in fresh)
        return {
            "signals_24h": len(fresh),
            "avg_score": round(sum(x.score for x in fresh) / len(fresh), 3),
            "avg_final_score": round(sum(x.final_score for x in fresh) / len(fresh), 3),
            "avg_move_60s_pct": round(sum(x.move_60s_pct for x in fresh) / len(fresh), 3),
            "top_symbols": counter.most_common(5),
            "ml_scored_signals": sum(1 for x in fresh if x.ml_score is not None),
        }

    def health(self) -> dict[str, object]:
        return {
            "running": self.running,
            "connected_clients": len(self.clients),
            "signals_cached": len(self.signals),
            "last_market_caps_update": self.last_market_caps_update.isoformat()
            if self.last_market_caps_update
            else None,
            "detector_state": self.detector.snapshot_state(),
            "alert_config": self.safe_alert_config(),
            "report": self.report(),
        }
