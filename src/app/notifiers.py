from __future__ import annotations

import logging

import httpx

from app.config import AlertConfig
from app.models import PumpSignal

logger = logging.getLogger(__name__)


class AlertDispatcher:
    def __init__(self, config: AlertConfig) -> None:
        self.config = config

    def update_config(self, config: AlertConfig) -> None:
        self.config = config

    async def dispatch(self, signal: PumpSignal) -> None:
        if not self.config.enabled:
            return
        if signal.score < self.config.min_score_for_alert:
            return
        text = self._format_message(signal)

        if self.config.telegram_bot_token and self.config.telegram_chat_id:
            await self._send_telegram(text)
        if self.config.webhook_url:
            await self._send_webhook(signal, text)

    async def _send_telegram(self, text: str) -> None:
        url = f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"
        payload = {"chat_id": self.config.telegram_chat_id, "text": text}
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
        logger.info("Telegram alert sent")

    async def _send_webhook(self, signal: PumpSignal, text: str) -> None:
        payload = {
            "message": text,
            "symbol": signal.symbol,
            "score": signal.score,
            "move_60s_pct": signal.move_60s_pct,
            "take_profit_pct": signal.suggested_take_profit_pct,
            "stop_loss_pct": signal.suggested_stop_loss_pct,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(self.config.webhook_url, json=payload)
            response.raise_for_status()
        logger.info("Webhook alert sent")

    @staticmethod
    def _format_message(signal: PumpSignal) -> str:
        return (
            "🚀 Early pump signal\n"
            f"Symbol: {signal.symbol}\n"
            f"Score: {signal.score}\n"
            f"Move 60s: {signal.move_60s_pct}%\n"
            f"Volume spike: {signal.volume_spike_ratio}x\n"
            f"TP: {signal.suggested_take_profit_pct}% | SL: {signal.suggested_stop_loss_pct}%"
        )
