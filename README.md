# Bybit Early Pump Scanner (Web)

Веб-агент для **онлайн анализа рынка крипты** с фокусом на ранние импульсы в low-cap альткоинах Bybit (без автоторговли).

## Что делает
- Сканирует Bybit linear USDT-пары в реальном времени.
- Фильтрует low/mid-cap альты по market cap (CoinGecko cache).
- Игнорирует микродвижения: минимум по умолчанию `3%` за 60с.
- Комбинирует rule-based и (опционально) ML-score (CatBoost), если модель загружена.
- Показывает расширенные признаки сигнала:
  - `score`, `final_score`, `ml_score`
  - `regime`, `oi_delta_60s_pct`, `spread_bps`, `explanation`
  - ориентиры `take/stop`
- Позволяет менять пороги детектора в UI без перезапуска.
- Поддерживает алерты в Telegram/Webhook.
- Строит 24h-сводку по качеству сигналов.

## Архитектура
- `src/app/main.py` — FastAPI + WebSocket + HTTP API.
- `src/app/service.py` — online loop, broadcast, cache market caps, live-config, report.
- `src/app/detector.py` — детектор импульса + regime + blending rule/ML score.
- `src/app/ml.py` — загрузка/инференс CatBoost-модели.
- `src/app/notifiers.py` — отправка Telegram/Webhook алертов.
- `src/app/clients.py` — интеграции Bybit/CoinGecko.
- `src/app/templates/index.html` + `src/app/static/*` — UI.
- `scripts/backtest.py` — базовый backtest.
- `scripts/train_catboost.py` — обучение CatBoost модели.

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

## Как включить ML (CatBoost)
1. Обучить модель:
```bash
python scripts/train_catboost.py --symbols WIFUSDT DOGEUSDT PEPEUSDT --limit 1200
```
2. Убедиться, что файл `artifacts/catboost_pump.cbm` создан.
3. Перезапустить приложение.
4. В `/api/health` поле `detector_state.ml_model_loaded` должно стать `true`.

## Как добавить алерты
1. В UI включить `enabled` в блоке **Алерты**.
2. Для Telegram заполнить `telegram_bot_token` и `telegram_chat_id`.
3. Для webhook заполнить `webhook_url`.
4. Установить `min_score_for_alert`.

## Важно
- Это исследовательский аналитический инструмент, **не финансовая рекомендация**.
- Автоторговля намеренно не реализована.
