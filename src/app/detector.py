from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta

from app.config import DetectorConfig
from app.models import PumpSignal, TickSnapshot


class PumpDetector:
    def __init__(self, config: DetectorConfig) -> None:
        self.config = config
        self.history: dict[str, deque[TickSnapshot]] = defaultdict(deque)
        self.last_signal_at: dict[str, datetime] = {}

    def ingest(
        self,
        ticks: list[TickSnapshot],
        market_caps: dict[str, float],
    ) -> list[PumpSignal]:
        signals: list[PumpSignal] = []
        for tick in ticks:
            base = tick.symbol.removesuffix(self.config.quote_asset)
            cap = market_caps.get(base)
            if cap is None:
                continue
            if not (self.config.min_market_cap_usd <= cap <= self.config.max_market_cap_usd):
                continue
            history = self.history[tick.symbol]
            history.append(tick)
            cutoff = tick.ts - timedelta(seconds=self.config.lookback_seconds)
            while history and history[0].ts < cutoff:
                history.popleft()
            signal = self._score_symbol(tick.symbol)
            if signal:
                signals.append(signal)
        return signals

    def _score_symbol(self, symbol: str) -> PumpSignal | None:
        series = self.history[symbol]
        if len(series) < 6:
            return None

        last = series[-1]
        p_now = last.price

        p_15 = self._price_seconds_ago(series, 15)
        p_60 = self._price_seconds_ago(series, 60)
        v_15 = self._volume_seconds_ago(series, 15)
        v_60 = self._volume_seconds_ago(series, 60)

        if p_15 <= 0 or p_60 <= 0 or v_15 <= 0 or v_60 <= 0:
            return None

        move_15 = (p_now / p_15 - 1) * 100
        move_60 = (p_now / p_60 - 1) * 100
        volume_spike_ratio = (v_15 / 15) / (v_60 / 60)

        early_factor = max(0.0, 1 - abs(move_15 - move_60) / max(abs(move_60), 0.01))
        momentum_factor = min(1.0, max(0.0, move_60 / 8))
        volume_factor = min(1.0, max(0.0, (volume_spike_ratio - 1) / 2))

        score = 0.45 * early_factor + 0.35 * momentum_factor + 0.20 * volume_factor

        if move_60 < self.config.min_move_pct:
            return None
        if volume_spike_ratio < self.config.min_volume_spike_ratio:
            return None
        if score < self.config.min_score:
            return None

        previous = self.last_signal_at.get(symbol)
        if previous and (last.ts - previous).total_seconds() < self.config.signal_cooldown_seconds:
            return None

        self.last_signal_at[symbol] = last.ts

        tp = max(move_60 * 0.8, self.config.min_move_pct)
        sl = max(1.5, min(move_60 * 0.35, 4.0))

        return PumpSignal(
            symbol=symbol,
            score=round(score, 3),
            move_15s_pct=round(move_15, 2),
            move_60s_pct=round(move_60, 2),
            volume_spike_ratio=round(volume_spike_ratio, 2),
            suggested_take_profit_pct=round(tp, 2),
            suggested_stop_loss_pct=round(sl, 2),
            price=round(p_now, 8),
        )

    @staticmethod
    def _price_seconds_ago(series: deque[TickSnapshot], seconds: int) -> float:
        threshold = series[-1].ts - timedelta(seconds=seconds)
        for item in reversed(series):
            if item.ts <= threshold:
                return item.price
        return series[0].price

    @staticmethod
    def _volume_seconds_ago(series: deque[TickSnapshot], seconds: int) -> float:
        threshold = series[-1].ts - timedelta(seconds=seconds)
        for item in reversed(series):
            if item.ts <= threshold:
                baseline = item.volume_24h
                current = series[-1].volume_24h
                return max(current - baseline, 0.0)
        return max(series[-1].volume_24h - series[0].volume_24h, 0.0)

    def snapshot_state(self) -> dict[str, object]:
        return {
            "tracked_symbols": len(self.history),
            "last_signals": {k: v.isoformat() for k, v in self.last_signal_at.items()},
            "config": self.config.model_dump(),
        }
