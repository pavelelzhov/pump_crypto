from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class TickSnapshot:
    symbol: str
    price: float
    volume_24h: float
    ts: datetime


@dataclass(slots=True)
class PumpSignal:
    symbol: str
    score: float
    move_15s_pct: float
    move_60s_pct: float
    volume_spike_ratio: float
    suggested_take_profit_pct: float
    suggested_stop_loss_pct: float
    price: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
