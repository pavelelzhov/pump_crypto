from datetime import datetime, timedelta

from app.config import DetectorConfig
from app.detector import PumpDetector
from app.models import TickSnapshot


def test_detects_early_pump_signal() -> None:
    cfg = DetectorConfig(min_move_pct=3.0, min_score=0.1, min_volume_spike_ratio=1.0)
    detector = PumpDetector(cfg)
    now = datetime.utcnow()
    ticks = []
    for i in range(20):
        ts = now + timedelta(seconds=i * 5)
        price = 1.0 + (i * 0.004)
        if i > 14:
            price += (i - 14) * 0.02
        vol = 1_000_000 + i * 20_000
        ticks.append(TickSnapshot(symbol="TESTUSDT", price=price, volume_24h=vol, ts=ts))

    signals = detector.ingest(ticks, {"TEST": 150_000_000})
    assert signals
    assert signals[-1].move_60s_pct >= cfg.min_move_pct


def test_ignores_large_cap_assets() -> None:
    cfg = DetectorConfig()
    detector = PumpDetector(cfg)
    now = datetime.utcnow()
    ticks = [
        TickSnapshot(
            symbol="BIGUSDT",
            price=1.0,
            volume_24h=1_000_000,
            ts=now + timedelta(seconds=i * 5),
        )
        for i in range(12)
    ]
    signals = detector.ingest(ticks, {"BIG": 15_000_000_000})
    assert signals == []
