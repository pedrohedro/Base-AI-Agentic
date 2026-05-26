"""
monitor.py — Lightweight market monitor for the Base AI Agentic trading agent.

Runs a 30-second polling loop without calling the LLM.
Only fires POST /api/chat when a real market trigger is detected,
reducing LLM API usage by ~95% compared to a blind 90-second heartbeat.

Start with: venv/bin/python monitor.py
HTTP status dashboard: http://localhost:8001/status
"""

import asyncio
import json
import logging
import os
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
import pandas as pd
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from hyperliquid.info import Info
from hyperliquid.utils import constants

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAIN_BACKEND = "http://localhost:8000"
MONITOR_PORT = 8001
LOOP_INTERVAL = 30          # seconds between polling cycles
LLM_COOLDOWN = 3600         # minimum seconds between LLM calls per asset
STATE_FILE = Path("trading_state.json")
MONITOR_STATE_FILE = Path("monitor_state.json")

MONITORED_ASSETS = ["ETH", "BTC", "DOGE"]

PYTH_FEEDS = {
    "ETH":  "0xff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace",
    "BTC":  "0xe62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43",
    "SOL":  "0xef0d8b6fda2ceba41da15d4095d1da392a0d2f8ed0c6c7bc0f4cfac8c280b56d",
    "DOGE": "0xdcef50dd0a4cd2dcc17e45df1676dcb336a11a61c69df7a0299b0150c672d25c",
    "USDC": "0xeaa020c61cc479712813461ce153894b96a6c00b21ed0cfc2798d1f9a9e9c94a",
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("monitor")

# ---------------------------------------------------------------------------
# Shared state (written by loop, read by HTTP server)
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_runtime: dict = {
    "last_prices": {},
    "last_rsi": {},
    "last_indicators": {},
    "open_positions": {},
    "last_trigger": None,
    "last_cycle_ts": None,
    "next_cycle_ts": None,
    "cycle_count": 0,
}

# ---------------------------------------------------------------------------
# Monitor state persistence
# ---------------------------------------------------------------------------

def _load_monitor_state() -> dict:
    if MONITOR_STATE_FILE.exists():
        try:
            return json.loads(MONITOR_STATE_FILE.read_text())
        except Exception:
            pass
    return {
        "last_llm_call": {a: 0 for a in MONITORED_ASSETS},
        "alerts": [],
        "last_prices": {},
        "last_rsi": {},
    }


def _save_monitor_state(state: dict) -> None:
    try:
        MONITOR_STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    except Exception as e:
        log.warning("Could not save monitor state: %s", e)


# ---------------------------------------------------------------------------
# Market data helpers (mirrors mcp_server.py logic, fully self-contained)
# ---------------------------------------------------------------------------

async def _fetch_pyth_price(asset: str) -> Optional[float]:
    feed_id = PYTH_FEEDS.get(asset.upper())
    if not feed_id:
        return None
    url = f"https://hermes.pyth.network/v2/updates/price/latest?ids[]={feed_id}"
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=10)
            r.raise_for_status()
            parsed = r.json().get("parsed", [])
            if not parsed:
                return None
            p = parsed[0]["price"]
            return float(p["price"]) * (10 ** int(p["expo"]))
    except Exception as e:
        log.debug("Pyth price fetch failed for %s: %s", asset, e)
        return None


def _fetch_hl_price(asset: str, info: Info) -> Optional[float]:
    try:
        mids = info.all_mids()
        return float(mids.get(asset.upper(), 0)) or None
    except Exception as e:
        log.debug("Hyperliquid price fallback failed for %s: %s", asset, e)
        return None


async def _fetch_price(asset: str, info: Info) -> Optional[float]:
    price = await _fetch_pyth_price(asset)
    if price:
        return price
    log.warning("Pyth unavailable for %s — falling back to Hyperliquid mid", asset)
    return _fetch_hl_price(asset, info)


def _calculate_indicators(asset: str, info: Info) -> Optional[dict]:
    try:
        end_ms = int(time.time() * 1000)
        start_ms = end_ms - 100 * 5 * 60 * 1000
        candles = info.candles_snapshot(asset.upper(), "5m", start_ms, end_ms)
        if not candles:
            return None

        df = pd.DataFrame([{
            "close": float(c["c"]),
            "high":  float(c["h"]),
            "low":   float(c["l"]),
            "vol":   float(c["v"]),
        } for c in candles])

        df["sma20"] = df["close"].rolling(20).mean()
        df["std20"] = df["close"].rolling(20).std()
        df["bb_upper"] = df["sma20"] + 2 * df["std20"]
        df["bb_lower"] = df["sma20"] - 2 * df["std20"]

        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 1e-9)
        df["rsi"] = 100 - (100 / (1 + gain / loss))

        r = df.iloc[-1]
        return {
            "close":    r["close"],
            "rsi":      r["rsi"],
            "bb_upper": r["bb_upper"],
            "bb_lower": r["bb_lower"],
            "sma20":    r["sma20"],
        }
    except Exception as e:
        log.warning("Indicator calculation failed for %s: %s", asset, e)
        return None


# ---------------------------------------------------------------------------
# Position state reader
# ---------------------------------------------------------------------------

def _read_open_positions() -> dict:
    try:
        data = json.loads(STATE_FILE.read_text())
        return data.get("simulated_hyperliquid_positions", {})
    except Exception as e:
        log.warning("Could not read trading_state.json: %s", e)
        return {}


def _read_sl_tp_targets() -> dict:
    try:
        data = json.loads(STATE_FILE.read_text())
        return data.get("futures_sl_tp_targets", {})
    except Exception as e:
        return {}


# ---------------------------------------------------------------------------
# LLM trigger logic
# ---------------------------------------------------------------------------

async def _call_llm(message: str) -> None:
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{MAIN_BACKEND}/api/chat",
                json={"message": message},
                timeout=60,
            )
            if r.status_code == 200:
                log.info("LLM call sent. Reply preview: %.120s", r.json().get("reply", ""))
            else:
                log.warning("LLM endpoint returned HTTP %s", r.status_code)
    except Exception as e:
        log.error("Failed to call LLM: %s", e)


def _posicao_str(positions: dict, asset: str) -> str:
    pos = positions.get(asset)
    if not pos:
        return "nenhuma"
    return f"{pos['side']} {pos['szi']} @ ${pos['entryPx']:.2f} (lev {pos['leverage']}x)"


def _evaluate_triggers(
    asset: str,
    close: float,
    rsi: float,
    bb_upper: float,
    bb_lower: float,
    positions: dict,
    sl_tp: dict,
    last_llm_call: dict,
    alerts: list,
) -> Optional[str]:
    now = time.time()
    cooldown_ok = (now - last_llm_call.get(asset, 0)) >= LLM_COOLDOWN
    posicao = _posicao_str(positions, asset)
    has_position = asset in positions
    target = sl_tp.get(asset, {})
    message = None
    trigger_name = None

    # SL/TP proximity checks take priority (always fire regardless of cooldown)
    if has_position and target:
        sl = target.get("sl")
        tp = target.get("tp")
        side = target.get("direction", "")
        entry = target.get("entry_px", 0)

        if sl:
            dist_sl = abs(close - sl) / sl * 100
            if dist_sl <= 1.0:
                trigger_name = "SL_PROXIMITY"
                message = (
                    f"URGENTE: {asset} a {dist_sl:.2f}% do Stop Loss (${sl}). "
                    f"Posição: {side} @ ${entry}. Avaliar fechamento."
                )

        if tp and not message:
            dist_tp = abs(close - tp) / tp * 100
            if dist_tp <= 1.5:
                trigger_name = "TP_PROXIMITY"
                message = (
                    f"ALERTA: {asset} a {dist_tp:.2f}% do Take Profit (${tp}). "
                    f"Confirmar ou ajustar target."
                )

    # RSI and Bollinger triggers (subject to cooldown)
    if not message and cooldown_ok:
        if rsi > 70:
            trigger_name = "RSI_OVERBOUGHT"
            message = (
                f"ALERTA: {asset} RSI={rsi:.1f} em sobrecompra. "
                f"Posição atual: {posicao}. Analisar e agir."
            )
        elif rsi < 30:
            trigger_name = "RSI_OVERSOLD"
            message = (
                f"ALERTA: {asset} RSI={rsi:.1f} em sobrevenda. "
                f"Posição atual: {posicao}. Analisar e agir."
            )
        elif close > bb_upper:
            trigger_name = "BB_BREAKOUT_UP"
            message = (
                f"ALERTA: {asset} rompeu BB superior (${close:.2f} > ${bb_upper:.2f}). "
                f"Posição: {posicao}. Analisar."
            )
        elif close < bb_lower:
            trigger_name = "BB_BREAKOUT_DOWN"
            message = (
                f"ALERTA: {asset} rompeu BB inferior (${close:.2f} < ${bb_lower:.2f}). "
                f"Posição: {posicao}. Analisar."
            )
        elif not has_position and (rsi > 65 or rsi < 35):
            trigger_name = "NO_POSITION"
            message = (
                f"Sem posição aberta. {asset} RSI={rsi:.1f}. "
                f"Avaliar abertura de posição."
            )

    if message:
        alert = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "asset": asset,
            "trigger": trigger_name,
            "message": message,
        }
        alerts.append(alert)
        if len(alerts) > 50:
            alerts[:] = alerts[-50:]
        log.info("TRIGGER [%s] %s: %s", trigger_name, asset, message[:100])

    return message, trigger_name


# ---------------------------------------------------------------------------
# Main monitoring loop
# ---------------------------------------------------------------------------

async def monitoring_loop() -> None:
    state = _load_monitor_state()
    info = Info(constants.TESTNET_API_URL, skip_ws=True)

    log.info("Monitor started. Loop interval=%ds, LLM cooldown=%ds", LOOP_INTERVAL, LLM_COOLDOWN)

    while True:
        cycle_start = time.time()

        with _lock:
            _runtime["last_cycle_ts"] = datetime.now(timezone.utc).isoformat()
            _runtime["cycle_count"] += 1

        positions = _read_open_positions()
        sl_tp = _read_sl_tp_targets()

        with _lock:
            _runtime["open_positions"] = positions

        for asset in MONITORED_ASSETS:
            try:
                price = await _fetch_price(asset, info)
                if price is None:
                    log.warning("No price available for %s, skipping", asset)
                    continue

                state["last_prices"][asset] = price
                with _lock:
                    _runtime["last_prices"][asset] = price

                indicators = _calculate_indicators(asset, info)
                if indicators is None:
                    log.warning("No indicators for %s, skipping trigger evaluation", asset)
                    continue

                rsi      = indicators["rsi"]
                bb_upper = indicators["bb_upper"]
                bb_lower = indicators["bb_lower"]
                close    = indicators["close"]

                state["last_rsi"][asset] = rsi
                with _lock:
                    _runtime["last_rsi"][asset] = rsi
                    _runtime["last_indicators"][asset] = indicators

                message, trigger_name = _evaluate_triggers(
                    asset, close, rsi, bb_upper, bb_lower,
                    positions, sl_tp,
                    state["last_llm_call"], state["alerts"],
                )

                if message:
                    with _lock:
                        _runtime["last_trigger"] = {
                            "asset": asset,
                            "trigger": trigger_name,
                            "message": message,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    # SL/TP proximity calls skip the cooldown update
                    if trigger_name not in ("SL_PROXIMITY", "TP_PROXIMITY"):
                        state["last_llm_call"][asset] = time.time()
                    await _call_llm(message)

            except Exception as e:
                log.error("Error processing %s: %s", asset, e)

        _save_monitor_state(state)

        elapsed = time.time() - cycle_start
        sleep_for = max(0, LOOP_INTERVAL - elapsed)

        next_ts = datetime.fromtimestamp(time.time() + sleep_for, tz=timezone.utc).isoformat()
        with _lock:
            _runtime["next_cycle_ts"] = next_ts

        log.debug("Cycle complete in %.1fs — sleeping %.1fs", elapsed, sleep_for)
        await asyncio.sleep(sleep_for)


# ---------------------------------------------------------------------------
# FastAPI HTTP server (runs in a background thread)
# ---------------------------------------------------------------------------

app = FastAPI(title="Trading Monitor", version="1.0.0")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/status")
def status_endpoint():
    with _lock:
        state = _load_monitor_state()
        return JSONResponse({
            "cycle_count":    _runtime["cycle_count"],
            "last_cycle_ts":  _runtime["last_cycle_ts"],
            "next_cycle_ts":  _runtime["next_cycle_ts"],
            "last_prices":    _runtime["last_prices"],
            "last_rsi":       _runtime["last_rsi"],
            "last_indicators": {
                asset: {k: round(v, 4) for k, v in ind.items()}
                for asset, ind in _runtime["last_indicators"].items()
            },
            "open_positions": _runtime["open_positions"],
            "last_trigger":   _runtime["last_trigger"],
            "llm_cooldown_remaining": {
                asset: max(0, round(LLM_COOLDOWN - (time.time() - ts)))
                for asset, ts in state.get("last_llm_call", {}).items()
            },
        })


@app.get("/alerts")
def alerts_endpoint():
    state = _load_monitor_state()
    alerts = state.get("alerts", [])
    return JSONResponse({"count": len(alerts), "alerts": list(reversed(alerts))})


def _run_http_server() -> None:
    uvicorn.run(app, host="0.0.0.0", port=MONITOR_PORT, log_level="warning")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    http_thread = threading.Thread(target=_run_http_server, daemon=True)
    http_thread.start()
    log.info("HTTP dashboard running at http://localhost:%d", MONITOR_PORT)

    asyncio.run(monitoring_loop())
