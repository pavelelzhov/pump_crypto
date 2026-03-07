from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app.config import DEFAULT_CONFIG
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
service = PumpScannerService(DEFAULT_CONFIG)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


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
        context={"config": DEFAULT_CONFIG.model_dump()},
    )


@app.get("/api/signals")
async def api_signals() -> dict[str, object]:
    return {"items": service.list_signals()}


@app.get("/api/health")
async def api_health() -> dict[str, object]:
    return service.health()


@app.websocket("/ws")
async def ws_feed(websocket: WebSocket) -> None:
    await service.register(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await service.unregister(websocket)
