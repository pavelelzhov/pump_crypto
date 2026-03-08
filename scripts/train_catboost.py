"""Train CatBoost model for early momentum continuation probability."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.metrics import roc_auc_score

from app.clients import BybitClient


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame()
    out["ret_1"] = df["close"].pct_change(1) * 100
    out["ret_3"] = df["close"].pct_change(3) * 100
    out["ret_5"] = df["close"].pct_change(5) * 100
    vol_short = df["turnover"].rolling(2).mean()
    vol_long = df["turnover"].rolling(8).mean()
    out["vol_spike"] = (vol_short / vol_long).replace([np.inf, -np.inf], np.nan)
    out["range_pct"] = ((df["high"] - df["low"]) / df["close"]).replace([np.inf, -np.inf], np.nan)
    out["ema_gap"] = (df["close"] / df["close"].ewm(span=10).mean() - 1) * 100
    out = out.dropna().reset_index(drop=True)
    return out


async def fetch_symbol(symbol: str, limit: int) -> pd.DataFrame:
    client = BybitClient()
    rows = await client.get_klines(symbol=symbol, limit=limit)
    rows = list(reversed(rows))
    data = []
    for r in rows:
        _, o, h, low, c, turnover, *_ = r
        data.append(
            {
                "open": float(o),
                "high": float(h),
                "low": float(low),
                "close": float(c),
                "turnover": float(turnover),
            }
        )
    return pd.DataFrame(data)


async def run(
    symbols: list[str],
    limit: int,
    out_path: str,
    horizon: int,
    target_move: float,
) -> None:
    frames = []
    for symbol in symbols:
        df = await fetch_symbol(symbol, limit)
        if df.empty:
            continue
        feat = build_features(df)
        aligned_close = df["close"].iloc[len(df) - len(feat) :].reset_index(drop=True)
        future = aligned_close.shift(-horizon)
        y = ((future / aligned_close - 1) * 100 >= target_move).astype(int)
        feat["target"] = y
        feat = feat.dropna().reset_index(drop=True)
        frames.append(feat)

    dataset = pd.concat(frames, ignore_index=True)
    X = dataset.drop(columns=["target"])
    y = dataset["target"]

    split = int(len(dataset) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    model = CatBoostClassifier(iterations=300, depth=6, learning_rate=0.05, verbose=False)
    model.fit(X_train, y_train)

    probs = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, probs) if len(set(y_test)) > 1 else 0.5

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(out))

    meta = {
        "symbols": symbols,
        "rows": int(len(dataset)),
        "features": list(X.columns),
        "horizon": horizon,
        "target_move": target_move,
        "auc": float(round(auc, 4)),
    }
    meta_path = out.parent / "catboost_pump_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", default=["WIFUSDT", "DOGEUSDT", "PEPEUSDT"])
    parser.add_argument("--limit", type=int, default=1200)
    parser.add_argument("--out", default="artifacts/catboost_pump.cbm")
    parser.add_argument("--horizon", type=int, default=5)
    parser.add_argument("--target-move", type=float, default=1.5)
    args = parser.parse_args()
    asyncio.run(run(args.symbols, args.limit, args.out, args.horizon, args.target_move))
