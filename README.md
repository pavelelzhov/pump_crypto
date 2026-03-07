# Bybit Early Pump Scanner (Web)

Веб-агент для **онлайн поиска зарождающихся пампов** в low-cap альткоинах на Bybit (без автоторговли).

## Что делает
- Сканирует Bybit linear USDT-пары в реальном времени.
- Фильтрует только low/mid-cap альты по market cap (CoinGecko cache).
- Игнорирует микродвижения: минимум по умолчанию `3%` за 60с (не 2%).
- Ищет **раннюю фазу**: ускорение цены + всплеск объема + скоринг.
- Для каждого сигнала дает ориентиры:
  - `suggested_take_profit_pct`
  - `suggested_stop_loss_pct`
- Показывает все в веб-интерфейсе и логирует работу в `logs/app.log`.

## Архитектура
- `src/app/main.py` — FastAPI + WebSocket + HTTP API.
- `src/app/service.py` — online loop, broadcast, cache market caps.
- `src/app/detector.py` — логика раннего детекта пампа.
- `src/app/clients.py` — интеграции Bybit/CoinGecko.
- `src/app/templates/index.html` + `src/app/static/*` — UI.
- `scripts/backtest.py` — бэктест на исторических свечах Bybit.

## Быстрый старт
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn app.main:app --reload --app-dir src
```
Открыть: `http://127.0.0.1:8000`

## API
- `GET /api/health`
- `GET /api/signals`
- `WS /ws`

## Конфиг
Основные параметры в `src/app/config.py`:
- `min_move_pct` (>=2, default=3)
- `max_market_cap_usd` (default=1.5B)
- `min_volume_spike_ratio`
- `min_score`

## Этапы разработки (суммаризация)
1. **Этап 1 — Core backend:** реализованы интеграции, детектор ранней фазы, online loop, логирование.
2. **Этап 2 — Web UI:** добавлен dashboard с live-таблицей сигналов по WebSocket.
3. **Этап 3 — Качество:** добавлены unit/API тесты, backtest script, static security scan (Bandit).

## Важно
- Это исследовательский аналитический инструмент, **не финансовая рекомендация**.
- Автоторговля намеренно не реализована.
