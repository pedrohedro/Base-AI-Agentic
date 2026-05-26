"""
strategy.py — Módulo de estratégias de trading quantitativo para o agente autônomo.
Todas as funções são síncronas e devem ser chamadas via run_in_executor.
"""
import time
import numpy as np
import pandas as pd
from hyperliquid.info import Info
from hyperliquid.utils import constants


# ---------------------------------------------------------------------------
# Fetchers
# ---------------------------------------------------------------------------

def _fetch_candles(asset: str, n: int = 200) -> pd.DataFrame:
    info = Info(constants.TESTNET_API_URL, skip_ws=True)
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - n * 5 * 60 * 1000

    candles = info.candles_snapshot(asset.upper(), "5m", start_ms, end_ms)
    if not candles:
        raise ValueError(f"Sem dados de velas para {asset.upper()} na Hyperliquid testnet.")

    df = pd.DataFrame([{
        "open":  float(c["o"]),
        "high":  float(c["h"]),
        "low":   float(c["l"]),
        "close": float(c["c"]),
        "vol":   float(c["v"]),
    } for c in candles])
    return df


# ---------------------------------------------------------------------------
# Indicadores auxiliares
# ---------------------------------------------------------------------------

def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean().replace(0, 1e-9)
    return 100 - (100 / (1 + gain / loss))


def _compute_ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _compute_bollinger(series: pd.Series, period: int = 20) -> tuple[pd.Series, pd.Series, pd.Series]:
    sma = series.rolling(period).mean()
    std = series.rolling(period).std()
    return sma + 2 * std, sma, sma - 2 * std


def _compute_macd(series: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema12 = _compute_ema(series, 12)
    ema26 = _compute_ema(series, 26)
    macd_line = ema12 - ema26
    signal_line = _compute_ema(macd_line, 9)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


# ---------------------------------------------------------------------------
# 1. Confluência de indicadores
# ---------------------------------------------------------------------------

def analyze_confluence(asset_data: dict) -> dict:
    """
    Recebe snapshot de indicadores e retorna análise de confluência ponderada.

    asset_data esperado:
        close, rsi, bb_upper, bb_lower, macd_hist, ema50, ema200
    """
    close    = asset_data["close"]
    rsi      = asset_data["rsi"]
    bb_upper = asset_data["bb_upper"]
    bb_lower = asset_data["bb_lower"]
    hist     = asset_data["macd_hist"]
    ema50    = asset_data.get("ema50")
    ema200   = asset_data.get("ema200")

    long_votes  = 0
    short_votes = 0
    reasons_long  = []
    reasons_short = []

    # RSI
    if rsi < 30:
        long_votes += 2
        reasons_long.append(f"RSI em sobrevenda ({rsi:.1f})")
    elif rsi < 45:
        long_votes += 1
        reasons_long.append(f"RSI abaixo de 45 ({rsi:.1f})")
    elif rsi > 70:
        short_votes += 2
        reasons_short.append(f"RSI em sobrecompra ({rsi:.1f})")
    elif rsi > 55:
        short_votes += 1
        reasons_short.append(f"RSI acima de 55 ({rsi:.1f})")

    # Bollinger Bands
    if close < bb_lower:
        long_votes += 2
        reasons_long.append(f"Preço abaixo da BB inferior (${bb_lower:.2f})")
    elif close < (bb_lower + (bb_upper - bb_lower) * 0.25):
        long_votes += 1
        reasons_long.append("Preço no quartil inferior das BB")
    elif close > bb_upper:
        short_votes += 2
        reasons_short.append(f"Preço acima da BB superior (${bb_upper:.2f})")
    elif close > (bb_upper - (bb_upper - bb_lower) * 0.25):
        short_votes += 1
        reasons_short.append("Preço no quartil superior das BB")

    # MACD histogram
    if hist > 0:
        long_votes += 1
        reasons_long.append(f"MACD histograma positivo ({hist:.4f})")
    else:
        short_votes += 1
        reasons_short.append(f"MACD histograma negativo ({hist:.4f})")

    # EMA trend
    if ema50 is not None and ema200 is not None:
        if ema50 > ema200:
            long_votes += 1
            reasons_long.append(f"EMA50 acima da EMA200 (tendência de alta)")
        else:
            short_votes += 1
            reasons_short.append(f"EMA50 abaixo da EMA200 (tendência de baixa)")

    total_votes = long_votes + short_votes
    if total_votes == 0:
        score = 50.0
        signal = "HOLD"
        reasons = ["Sem votos — mercado neutro"]
    else:
        if long_votes > short_votes:
            score = 50 + (long_votes / (total_votes + 1)) * 50
            signal = "LONG"
            reasons = reasons_long
        elif short_votes > long_votes:
            score = 50 + (short_votes / (total_votes + 1)) * 50
            signal = "SHORT"
            reasons = reasons_short
        else:
            score = 50.0
            signal = "HOLD"
            reasons = ["Votos empatados — aguardar confirmação"]

    if score >= 75:
        confidence = "high"
    elif score >= 65:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "signal": signal if score >= 65 else "HOLD",
        "score": round(score, 2),
        "confidence": confidence,
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# 2. Detecção de tendência macro
# ---------------------------------------------------------------------------

def detect_trend(candles: list) -> dict:
    """
    Detecta tendência macro usando EMA50 e EMA200 sobre lista de closes.

    candles: lista de dicts com chave 'close'
    """
    closes = pd.Series([float(c["close"]) for c in candles])

    if len(closes) < 200:
        ema50_val  = float(_compute_ema(closes, 50).iloc[-1])
        ema200_val = float(_compute_ema(closes, min(len(closes) - 1, 200)).iloc[-1])
    else:
        ema50_val  = float(_compute_ema(closes, 50).iloc[-1])
        ema200_val = float(_compute_ema(closes, 200).iloc[-1])

    spread_pct = (ema50_val - ema200_val) / ema200_val * 100

    if spread_pct > 1.0:
        trend = "UPTREND"
    elif spread_pct < -1.0:
        trend = "DOWNTREND"
    else:
        trend = "SIDEWAYS"

    return {
        "trend": trend,
        "strength": round(abs(spread_pct), 3),
        "ema50": round(ema50_val, 4),
        "ema200": round(ema200_val, 4),
        "spread_pct": round(spread_pct, 3),
    }


# ---------------------------------------------------------------------------
# 3. ATR para dimensionamento dinâmico de SL/TP
# ---------------------------------------------------------------------------

def calculate_atr(candles: list, period: int = 14) -> float:
    """
    Calcula o Average True Range (ATR) para os últimos `period` candles.

    candles: lista de dicts com chaves 'high', 'low', 'close'
    """
    highs  = pd.Series([float(c["high"])  for c in candles])
    lows   = pd.Series([float(c["low"])   for c in candles])
    closes = pd.Series([float(c["close"]) for c in candles])

    prev_close = closes.shift(1)
    tr = pd.concat([
        highs - lows,
        (highs - prev_close).abs(),
        (lows  - prev_close).abs(),
    ], axis=1).max(axis=1)

    return float(tr.rolling(period).mean().iloc[-1])


# ---------------------------------------------------------------------------
# 4. Detecção de divergência RSI / preço
# ---------------------------------------------------------------------------

def detect_divergence(closes: list, rsi_values: list) -> dict:
    """
    Detecta divergência clássica entre RSI e preço nos últimos N pontos.

    Retorna tipo (BULLISH / BEARISH / NONE) e força normalizada 0-1.
    """
    window = 20
    c_series   = pd.Series(closes[-window:]).reset_index(drop=True)
    rsi_series = pd.Series(rsi_values[-window:]).reset_index(drop=True)

    # Mínimos locais (bullish divergence)
    price_mins = []
    rsi_mins   = []
    for i in range(1, len(c_series) - 1):
        if c_series[i] < c_series[i - 1] and c_series[i] < c_series[i + 1]:
            price_mins.append((i, c_series[i]))
            rsi_mins.append((i, rsi_series[i]))

    # Máximos locais (bearish divergence)
    price_maxs = []
    rsi_maxs   = []
    for i in range(1, len(c_series) - 1):
        if c_series[i] > c_series[i - 1] and c_series[i] > c_series[i + 1]:
            price_maxs.append((i, c_series[i]))
            rsi_maxs.append((i, rsi_series[i]))

    # Bullish: 2 mínimos onde preço cai mas RSI sobe
    if len(price_mins) >= 2 and len(rsi_mins) >= 2:
        p1, p2 = price_mins[-2][1], price_mins[-1][1]
        r1, r2 = rsi_mins[-2][1],   rsi_mins[-1][1]
        if p2 < p1 and r2 > r1:
            strength = min(abs(r2 - r1) / 10, 1.0)
            return {"type": "BULLISH", "strength": round(strength, 3)}

    # Bearish: 2 máximos onde preço sobe mas RSI cai
    if len(price_maxs) >= 2 and len(rsi_maxs) >= 2:
        p1, p2 = price_maxs[-2][1], price_maxs[-1][1]
        r1, r2 = rsi_maxs[-2][1],   rsi_maxs[-1][1]
        if p2 > p1 and r2 < r1:
            strength = min(abs(r1 - r2) / 10, 1.0)
            return {"type": "BEARISH", "strength": round(strength, 3)}

    return {"type": "NONE", "strength": 0.0}


# ---------------------------------------------------------------------------
# 5. Sinal composto — função principal
# ---------------------------------------------------------------------------

def get_composite_signal(asset: str) -> dict:
    """
    Orquestra todos os indicadores e retorna decisão final de trading.

    Retorna dict com:
        asset, signal, confidence, score, reasons,
        suggested_sl_pct, suggested_tp_pct, raw_indicators
    """
    df = _fetch_candles(asset, n=220)

    df["rsi"]      = _compute_rsi(df["close"], 14)
    df["ema50"]    = _compute_ema(df["close"], 50)
    df["ema200"]   = _compute_ema(df["close"], 200)
    df["bb_upper"], df["bb_mid"], df["bb_lower"] = _compute_bollinger(df["close"])
    df["macd"], df["macd_sig"], df["macd_hist"] = _compute_macd(df["close"])

    last = df.iloc[-1]
    candle_records = df.to_dict("records")

    # ATR e SL/TP dinâmicos
    atr = calculate_atr(candle_records, period=14)
    sl_pct = round((1.5 * atr / float(last["close"])) * 100, 2)
    tp_pct = round((3.0 * atr / float(last["close"])) * 100, 2)
    sl_pct = max(sl_pct, 1.0)
    tp_pct = max(tp_pct, 2.0)

    # Tendência macro
    trend_data = detect_trend(candle_records)

    # Divergência RSI
    closes_list    = df["close"].tolist()
    rsi_list       = df["rsi"].dropna().tolist()
    divergence     = detect_divergence(closes_list, rsi_list)

    # Snapshot para confluência
    asset_snapshot = {
        "close":     float(last["close"]),
        "rsi":       float(last["rsi"]),
        "bb_upper":  float(last["bb_upper"]),
        "bb_lower":  float(last["bb_lower"]),
        "macd_hist": float(last["macd_hist"]),
        "ema50":     float(last["ema50"]),
        "ema200":    float(last["ema200"]),
    }
    confluence = analyze_confluence(asset_snapshot)

    # Bonus de score por divergência confirmada
    if divergence["type"] == "BULLISH" and confluence["signal"] == "LONG":
        confluence["score"] = min(confluence["score"] + divergence["strength"] * 10, 100)
        confluence["reasons"].append(f"Divergencia RSI bullish confirmada (forca {divergence['strength']:.2f})")
    elif divergence["type"] == "BEARISH" and confluence["signal"] == "SHORT":
        confluence["score"] = min(confluence["score"] + divergence["strength"] * 10, 100)
        confluence["reasons"].append(f"Divergencia RSI bearish confirmada (forca {divergence['strength']:.2f})")

    # Restrições de tendência
    signal = confluence["signal"]
    if signal == "LONG" and trend_data["trend"] == "DOWNTREND":
        signal = "HOLD"
        confluence["reasons"].append("LONG bloqueado — tendencia macro de baixa (EMA50 < EMA200)")
    if signal == "SHORT" and trend_data["trend"] == "UPTREND":
        signal = "HOLD"
        confluence["reasons"].append("SHORT bloqueado — tendencia macro de alta (EMA50 > EMA200)")

    # Threshold mínimo de score
    if confluence["score"] < 65:
        signal = "HOLD"

    # Reconstrói confidence após ajustes
    score = round(confluence["score"], 2)
    if score >= 75:
        confidence = "high"
    elif score >= 65:
        confidence = "medium"
    else:
        confidence = "low"

    confluence["reasons"].append(f"Tendencia macro: {trend_data['trend']} (spread EMA {trend_data['spread_pct']:.2f}%)")

    return {
        "asset": asset.upper(),
        "signal": signal,
        "confidence": confidence,
        "score": score,
        "reasons": confluence["reasons"],
        "suggested_sl_pct": sl_pct,
        "suggested_tp_pct": tp_pct,
        "raw_indicators": {
            "close":       round(float(last["close"]), 4),
            "rsi":         round(float(last["rsi"]), 2),
            "bb_upper":    round(float(last["bb_upper"]), 4),
            "bb_mid":      round(float(last["bb_mid"]), 4),
            "bb_lower":    round(float(last["bb_lower"]), 4),
            "macd":        round(float(last["macd"]), 6),
            "macd_signal": round(float(last["macd_sig"]), 6),
            "macd_hist":   round(float(last["macd_hist"]), 6),
            "ema50":       round(float(last["ema50"]), 4),
            "ema200":      round(float(last["ema200"]), 4),
            "atr":         round(atr, 4),
            "trend":       trend_data["trend"],
            "trend_strength": trend_data["strength"],
            "divergence":  divergence["type"],
            "divergence_strength": divergence["strength"],
        },
    }
