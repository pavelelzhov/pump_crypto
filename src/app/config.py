from pydantic import BaseModel, Field


class AlertConfig(BaseModel):
    enabled: bool = False
    min_score_for_alert: float = Field(default=0.8, ge=0.0, le=1.0)
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    webhook_url: str = ""


class DetectorConfig(BaseModel):
    quote_asset: str = "USDT"
    min_move_pct: float = Field(default=3.0, ge=2.0, description="Ignore smaller movements")
    min_market_cap_usd: float = 20_000_000
    max_market_cap_usd: float = 1_500_000_000
    min_volume_spike_ratio: float = 1.2
    min_score: float = 0.65
    lookback_seconds: int = 180
    poll_interval_seconds: float = 5.0
    signal_cooldown_seconds: int = 120


DEFAULT_CONFIG = DetectorConfig()
DEFAULT_ALERT_CONFIG = AlertConfig()
