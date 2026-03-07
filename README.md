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
- Позволяет менять пороги детектора в UI без перезапуска.
- Поддерживает алерты в Telegram/Webhook для high-score сигналов.
- Строит 24h-сводку по качеству/частоте сигналов.

## Архитектура
- `src/app/main.py` — FastAPI + WebSocket + HTTP API.
- `src/app/service.py` — online loop, broadcast, cache market caps, live-config, report.
- `src/app/detector.py` — логика раннего детекта пампа.
- `src/app/notifiers.py` — отправка Telegram/Webhook алертов.
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
- `GET /api/config`
- `POST /api/config`
- `POST /api/alerts`
- `GET /api/report`
- `WS /ws`

## Как добавить алерты
1. В UI включить `enabled` в блоке **Алерты**.
2. Для Telegram заполнить `telegram_bot_token` и `telegram_chat_id`.
3. Для webhook заполнить `webhook_url`.
4. Установить `min_score_for_alert`.

## Конфиг
Основные параметры в `src/app/config.py`:
- `min_move_pct` (>=2, default=3)
- `max_market_cap_usd` (default=1.5B)
- `min_volume_spike_ratio`
- `min_score`

## Важно
- Это исследовательский аналитический инструмент, **не финансовая рекомендация**.
- Автоторговля намеренно не реализована.
