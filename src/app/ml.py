from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class MLPumpScorer:
    def __init__(self, model_path: str = "artifacts/catboost_pump.cbm") -> None:
        self.model_path = Path(model_path)
        self.model = None
        self.available = False
        self._try_load()

    def _try_load(self) -> None:
        if not self.model_path.exists():
            logger.info("ML model not found at %s, fallback to rule-based scoring", self.model_path)
            return
        try:
            from catboost import CatBoostClassifier

            model = CatBoostClassifier()
            model.load_model(str(self.model_path))
            self.model = model
            self.available = True
            logger.info("Loaded CatBoost model from %s", self.model_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Unable to load CatBoost model: %s", exc)
            self.model = None
            self.available = False

    def predict_score(self, features: list[float]) -> float | None:
        if not self.available or self.model is None:
            return None
        try:
            proba = self.model.predict_proba([features])[0][1]
            return float(proba)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ML inference error: %s", exc)
            return None
