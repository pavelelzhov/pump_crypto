from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta

from app.config import DetectorConfig
from app.ml import MLPumpScorer
from app.models import PumpSignal, TickSnapshot


class PumpDetector:
    def __init__(self, config: DetectorConfig, ml_scorer: MLPumpScorer | None = None) -> None:
        self.config = config
        self.history: dict[str, deque[TickSnapshot]] = defaultdict(deque)
        self.last_signal_at: dict[str, datetime] = {}
        self.ml_scorer = ml_scorer or MLPumpScorer()

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
        oi_60 = self._oi_delta_60s_pct(series)
        spread_bps = self._spread_bps(last)

        if p_15 <= 0 or p_60 <= 0 or v_15 <= 0 or v_60 <= 0:
            return None

        move_15 = (p_now / p_15 - 1) * 100
        move_60 = (p_now / p_60 - 1) * 100
        volume_spike_ratio = (v_15 / 15) / (v_60 / 60)

        early_factor = max(0.0, 1 - abs(move_15 - move_60) / max(abs(move_60), 0.01))
        momentum_factor = min(1.0, max(0.0, move_60 / 8))
        volume_factor = min(1.0, max(0.0, (volume_spike_ratio - 1) / 2))

        score = 0.45 * early_factor + 0.35 * momentum_factor + 0.20 * volume_factor

        features = [move_15, move_60, volume_spike_ratio, oi_60, spread_bps, score]
        ml_score = self.ml_scorer.predict_score(features)
        final_score = score if ml_score is None else 0.60 * score + 0.40 * ml_score

        if move_60 < self.config.min_move_pct:
            return None
        if volume_spike_ratio < self.config.min_volume_spike_ratio:
            return None
        if final_score < self.config.min_score:
            return None

        previous = self.last_signal_at.get(symbol)
        if previous and (last.ts - previous).total_seconds() < self.config.signal_cooldown_seconds:
            return None

        self.last_signal_at[symbol] = last.ts
        regime = self._regime(move_60, volume_spike_ratio, spread_bps)

        tp_multiplier = 0.95 if regime == "trend" else 0.75
        sl_multiplier = 0.30 if regime == "trend" else 0.38
        tp = max(move_60 * tp_multiplier, self.config.min_move_pct)
        sl = max(1.2, min(move_60 * sl_multiplier, 4.2))

        explanation = (
            f"move60={move_60:.2f}% volSpike={volume_spike_ratio:.2f}x "
            f"oi60={oi_60:.2f}% spread={spread_bps:.2f}bps regime={regime}"
        )

        return PumpSignal(
            symbol=symbol,
            score=round(score, 3),
            final_score=round(final_score, 3),
            ml_score=round(ml_score, 3) if ml_score is not None else None,
            move_15s_pct=round(move_15, 2),
            move_60s_pct=round(move_60, 2),
            volume_spike_ratio=round(volume_spike_ratio, 2),
            oi_delta_60s_pct=round(oi_60, 2),
            spread_bps=round(spread_bps, 2),
            regime=regime,
            explanation=explanation,
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

    @staticmethod
    def _oi_delta_60s_pct(series: deque[TickSnapshot]) -> float:
        threshold = series[-1].ts - timedelta(seconds=60)
        for item in reversed(series):
            if item.ts <= threshold and item.open_interest > 0:
                return (series[-1].open_interest / item.open_interest - 1) * 100
        first = series[0]
        if first.open_interest <= 0:
            return 0.0
        return (series[-1].open_interest / first.open_interest - 1) * 100

    @staticmethod
    def _spread_bps(tick: TickSnapshot) -> float:
        if tick.bid1_price <= 0 or tick.ask1_price <= 0 or tick.price <= 0:
            return 0.0
        spread = tick.ask1_price - tick.bid1_price
        return (spread / tick.price) * 10000

    @staticmethod
    def _regime(move_60: float, vol_spike: float, spread_bps: float) -> str:
        if move_60 > 5 and vol_spike > 2:
            return "trend"
        if spread_bps > 20 or vol_spike > 3.5:
            return "volatile"
        return "normal"

    def snapshot_state(self) -> dict[str, object]:
        return {
            "tracked_symbols": len(self.history),
            "last_signals": {k: v.isoformat() for k, v in self.last_signal_at.items()},
            "config": self.config.model_dump(),
            "ml_model_loaded": self.ml_scorer.available,
        }
