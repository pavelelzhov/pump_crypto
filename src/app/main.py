from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request

from app.config import DEFAULT_ALERT_CONFIG, DEFAULT_CONFIG
from app.service import PumpScannerService

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

app = FastAPI(title="Bybit Early Pump Scanner")
service = PumpScannerService(DEFAULT_CONFIG, DEFAULT_ALERT_CONFIG)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


class ConfigUpdate(BaseModel):
    min_move_pct: float | None = None
    min_market_cap_usd: float | None = None
    max_market_cap_usd: float | None = None
    min_volume_spike_ratio: float | None = None
    min_score: float | None = None
    poll_interval_seconds: float | None = None
    signal_cooldown_seconds: int | None = None


class AlertConfigUpdate(BaseModel):
    enabled: bool | None = None
    min_score_for_alert: float | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    webhook_url: str | None = None


@app.on_event("startup")
async def startup_event() -> None:
    await service.start()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await service.stop()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "config": DEFAULT_CONFIG.model_dump(),
            "alert_config": DEFAULT_ALERT_CONFIG.model_dump(),
        },
    )


@app.get("/api/signals")
async def api_signals() -> dict[str, object]:
    return {"items": service.list_signals()}


@app.get("/api/health")
async def api_health() -> dict[str, object]:
    return service.health()


@app.get("/api/config")
async def api_get_config() -> dict[str, object]:
    return {
        "config": service.config.model_dump(),
        "alert_config": service.safe_alert_config(),
    }


@app.post("/api/config")
async def api_update_config(payload: ConfigUpdate) -> dict[str, object]:
    updated = service.update_config(payload.model_dump(exclude_none=True))
    return {"config": updated.model_dump()}


@app.post("/api/alerts")
async def api_update_alerts(payload: AlertConfigUpdate) -> dict[str, object]:
    updated = service.update_alert_config(payload.model_dump(exclude_none=True))
    return {"alert_config": service.safe_alert_config(), "enabled": updated.enabled}


@app.get("/api/report")
async def api_report() -> dict[str, object]:
    return service.report()


@app.websocket("/ws")
async def ws_feed(websocket: WebSocket) -> None:
    await service.register(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await service.unregister(websocket)
