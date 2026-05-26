import os
import json
import asyncio
import logging
import datetime
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import requests

from trading_agent import create_trading_agent, initialize_wallet_provider
import trading_agent

# Configuração de logs
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("trading_backend")

# Inicialização do FastAPI
app = FastAPI(title="Base Autonomous Trading Agent Dashboard")

# Permitir CORS para chamadas locais/frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar a carteira e o agente
wallet_provider = None
agent = None
agent_initialized = False

try:
    wallet_provider = initialize_wallet_provider()
    logger.info(f"Carteira carregada com sucesso: {wallet_provider.get_address()}")
except Exception as e:
    logger.error(f"Erro ao carregar carteira: {e}")

try:
    agent, _ = create_trading_agent()
    agent_initialized = True
except Exception as e:
    logger.error(f"Erro ao inicializar o agente ReAct: {e}")

# Dados em memória para o Dashboard
agent_logs: List[Dict[str, Any]] = []
is_autonomous_running = False
chat_history: List[tuple] = []  # Histórico da conversa com o agente
trading_interval_seconds = 180  # Intervalo de análise do mercado (evita 429 rate limit da Gemini Free Tier)
wallet_address = wallet_provider.get_address() if wallet_provider else "Não inicializado"
network_id = os.getenv("NETWORK_ID", "base-sepolia")
STATE_FILE = "trading_state.json"

# Cache para os preços do Hyperliquid via WebSocket
hl_mids_cache = {}
hl_info_ws = None

def on_all_mids(msg):
    if isinstance(msg, dict) and msg.get("channel") == "allMids":
        mids_data = msg.get("data", {}).get("mids", {})
        if mids_data:
            hl_mids_cache.update(mids_data)

# ─── WebSocket connection manager ────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self._connections: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self._connections:
            self._connections.remove(ws)

    async def broadcast(self, payload: dict):
        if not self._connections:
            return
        dead = []
        for ws in self._connections:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_manager = ConnectionManager()

# Queue used to signal the broadcaster that a push is needed immediately
_broadcast_trigger: asyncio.Queue = None


def _get_broadcast_trigger() -> asyncio.Queue:
    global _broadcast_trigger
    if _broadcast_trigger is None:
        _broadcast_trigger = asyncio.Queue()
    return _broadcast_trigger


# ─── State helpers ────────────────────────────────────────────────────────────

def load_trading_state() -> Dict[str, Any]:
    """Carrega o histórico e estado do trading a partir de um arquivo JSON local."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "price_history" not in data:
                    data["price_history"] = []
                if "simulated_eth_balance" not in data:
                    data["simulated_eth_balance"] = 0.05
                if "simulated_usdc_balance" not in data:
                    data["simulated_usdc_balance"] = 100.0
                if "simulated_hyperliquid_balance" not in data:
                    data["simulated_hyperliquid_balance"] = 1000.0
                if "simulated_hyperliquid_positions" not in data:
                    data["simulated_hyperliquid_positions"] = {}
                if "futures_sl_tp_targets" not in data:
                    data["futures_sl_tp_targets"] = {}
                if "futures_trades_history" not in data:
                    data["futures_trades_history"] = []
                if "futures_pnl_history" not in data:
                    data["futures_pnl_history"] = []
                if "undistributed_profit" not in data:
                    data["undistributed_profit"] = 0.0
                return data
        except Exception as e:
            logger.error(f"Erro ao ler arquivo de estado: {e}")
    return {
        "average_buy_price": 0.0,
        "total_eth_bought": 0.0,
        "total_usdc_spent": 0.0,
        "total_trades": 0,
        "trades_history": [],
        "price_history": [],
        "simulated_eth_balance": 0.05,
        "simulated_usdc_balance": 100.0,
        "simulated_hyperliquid_balance": 1000.0,
        "simulated_hyperliquid_positions": {},
        "futures_sl_tp_targets": {},
        "futures_trades_history": [],
        "futures_pnl_history": [],
        "undistributed_profit": 0.0
    }

def save_trading_state(state: Dict[str, Any]):
    """Salva o estado atual do trading em um arquivo JSON local."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Erro ao salvar arquivo de estado: {e}")

def add_log(message: str, category: str = "info"):
    """Adiciona um log na lista em memória e sinaliza o broadcaster WebSocket."""
    log_entry = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "message": message,
        "category": category
    }
    agent_logs.append(log_entry)
    logger.info(f"[{category.upper()}] {message}")
    if len(agent_logs) > 200:
        agent_logs.pop(0)
    try:
        _get_broadcast_trigger().put_nowait(log_entry)
    except Exception:
        pass

# Inicializar os primeiros logs e carregar estado inicial
state = load_trading_state()
if agent_initialized:
    add_log(f"Agente inicializado com sucesso na rede {network_id}!", "system")
    add_log(f"Endereço da carteira: {wallet_address}", "wallet")
    add_log(f"Estado de trading carregado. Total de trades registrados: {state['total_trades']}", "system")
else:
    add_log("Falha ao inicializar o agente. Verifique suas chaves no arquivo .env.", "error")

def fetch_eth_price_pyth() -> float:
    """Busca o preço atual do ETH em USD usando a API pública do Pyth Network (Hermes)."""
    feed_id = "0xff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace"
    url = f"https://hermes.pyth.network/v2/updates/price/latest?ids[]={feed_id}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            parsed = data.get("parsed")
            if parsed and len(parsed) > 0:
                price_info = parsed[0]["price"]
                price = float(price_info["price"])
                expo = int(price_info["expo"])
                return price * (10 ** expo)
    except Exception as e:
        logger.error(f"Erro ao buscar preço do ETH via Pyth: {e}")
    return 0.0

def fetch_eth_price() -> float:
    """Busca o preço atual do ETH em USD, tentando primeiro CoinGecko e depois Pyth como fallback."""
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd",
            timeout=10
        )
        if response.status_code == 200:
            price = float(response.json()["ethereum"]["usd"])
            return price
    except Exception as e:
        logger.error(f"Erro ao buscar preço do ETH via CoinGecko: {e}")

    # Fallback para o Pyth Network
    pyth_price = fetch_eth_price_pyth()
    if pyth_price > 0.0:
        logger.info(f"Usando preço do Pyth como fallback: ${pyth_price:.2f}")
        return pyth_price

    return 2118.50

def fetch_eth_balance(address: str) -> float:
    """Busca o saldo de ETH diretamente da rede via RPC JSON-RPC, ou retorna o saldo simulado se DRY_RUN estiver ativo."""
    if os.getenv("DRY_RUN", "false").lower() == "true":
        state = load_trading_state()
        return float(state.get("simulated_eth_balance", 0.05))

    payload = {
        "jsonrpc": "2.0",
        "method": "eth_getBalance",
        "params": [address, "latest"],
        "id": 1
    }
    rpc_url = "https://mainnet.base.org" if network_id == "base-mainnet" else "https://sepolia.base.org"
    try:
        response = requests.post(rpc_url, json=payload, timeout=10)
        if response.status_code == 200:
            result = response.json().get("result")
            if result:
                return int(result, 16) / 1e18
    except Exception as e:
        logger.error(f"Erro ao obter saldo de ETH via RPC: {e}")
    return 0.0

def fetch_usdc_balance(address: str) -> float:
    """Busca o saldo do token USDC diretamente via RPC, ou retorna o saldo simulado se DRY_RUN estiver ativo."""
    if os.getenv("DRY_RUN", "false").lower() == "true":
        state = load_trading_state()
        return float(state.get("simulated_usdc_balance", 100.0))

    usdc_address = "0x833589fCD6eDb6E08f4c7C32D4f71b54bda02913" if network_id == "base-mainnet" else "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
    addr_clean = address.lower().replace("0x", "")
    data = "0x70a08231" + addr_clean.zfill(64)
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [{"to": usdc_address, "data": data}, "latest"],
        "id": 1
    }
    rpc_url = "https://mainnet.base.org" if network_id == "base-mainnet" else "https://sepolia.base.org"
    try:
        response = requests.post(rpc_url, json=payload, timeout=10)
        if response.status_code == 200:
            result = response.json().get("result")
            if result and result != "0x":
                return int(result, 16) / 1_000_000.0
    except Exception as e:
        logger.error(f"Erro ao obter saldo de USDC via RPC: {e}")
    return 0.0

def record_trade_deltas(old_eth: float, old_usdc: float, new_eth: float, new_usdc: float):
    """Compara saldos de antes e depois e grava transações de swap detectadas."""
    delta_eth = new_eth - old_eth
    delta_usdc = new_usdc - old_usdc

    # COMPRA de ETH: saldo de ETH aumentou e USDC diminuiu significativamente
    if delta_eth > 0.00001 and delta_usdc < -0.01:
        buy_eth = delta_eth
        spent_usdc = abs(delta_usdc)
        price = spent_usdc / buy_eth

        market_price = fetch_eth_price()
        if market_price > 0.0 and abs(price - market_price) / market_price > 0.15:
            logger.warning(
                f"[Aviso] Preço calculado do swap (${price:.2f}) desvia mais de 15% do preço de mercado (${market_price:.2f}). "
                f"Possível poluição por faucet ou depósito de ETH. Corrigindo quantidade de ETH comprada..."
            )
            price = market_price
            buy_eth = spent_usdc / price

        state = load_trading_state()
        state["total_eth_bought"] = state.get("total_eth_bought", 0.0) + buy_eth
        state["total_usdc_spent"] = state.get("total_usdc_spent", 0.0) + spent_usdc
        if state["total_eth_bought"] > 0:
            state["average_buy_price"] = state["total_usdc_spent"] / state["total_eth_bought"]
        state["total_trades"] = state.get("total_trades", 0) + 1

        trade_entry = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "BUY",
            "eth_amount": float(f"{buy_eth:.6f}"),
            "usdc_amount": float(f"{spent_usdc:.2f}"),
            "price": float(f"{price:.2f}"),
            "pnl": 0.0
        }
        state["trades_history"].append(trade_entry)
        save_trading_state(state)
        add_log(f"Trade Detectado: COMPRA de {buy_eth:.5f} ETH por {spent_usdc:.2f} USDC (Preço: ${price:.2f}/ETH)", "wallet")

    # VENDA de ETH: saldo de ETH diminuiu e USDC aumentou significativamente
    elif delta_eth < -0.00001 and delta_usdc > 0.01:
        sell_eth = abs(delta_eth)
        received_usdc = delta_usdc
        price = received_usdc / sell_eth

        market_price = fetch_eth_price()
        if market_price > 0.0 and abs(price - market_price) / market_price > 0.15:
            logger.warning(
                f"[Aviso] Preço calculado do swap (${price:.2f}) desvia mais de 15% do preço de mercado (${market_price:.2f}). "
                f"Possível poluição por depósito externo de USDC. Corrigindo quantidade de USDC recebida..."
            )
            price = market_price
            received_usdc = sell_eth * price

        state = load_trading_state()
        avg_buy_price = state.get("average_buy_price", 0.0)

        pnl = 0.0
        if avg_buy_price > 0.0:
            cost_basis = sell_eth * avg_buy_price
            pnl = received_usdc - cost_basis

        state["total_trades"] = state.get("total_trades", 0) + 1

        total_eth = state.get("total_eth_bought", 0.0)
        if total_eth >= sell_eth:
            new_total_eth = total_eth - sell_eth
            state["total_eth_bought"] = new_total_eth
            state["total_usdc_spent"] = new_total_eth * avg_buy_price
        else:
            state["total_eth_bought"] = 0.0
            state["total_usdc_spent"] = 0.0

        trade_entry = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "SELL",
            "eth_amount": float(f"{sell_eth:.6f}"),
            "usdc_amount": float(f"{received_usdc:.2f}"),
            "price": float(f"{price:.2f}"),
            "pnl": float(f"{pnl:.2f}")
        }
        state["trades_history"].append(trade_entry)
        add_log(f"Trade Detectado: VENDA de {sell_eth:.5f} ETH por {received_usdc:.2f} USDC (Preço: ${price:.2f}/ETH, Lucro Realizado: ${pnl:.2f})", "wallet")


# ─── Helpers to build the broadcast payload ──────────────────────────────────

async def _build_status_payload() -> dict:
    loop = asyncio.get_event_loop()
    if not wallet_provider:
        return {
            "status": "inativo",
            "network": network_id,
            "address": "Não inicializado",
            "balance": "0.00",
            "usdc_balance": "0.00",
            "average_buy_price": "0.00",
            "total_trades": 0,
            "autonomous_active": False,
            "trades_history": [],
            "coingecko_price": "0.00",
            "pyth_price": "0.00",
            "trend": "lateral",
            "price_history": []
        }
    eth_balance = await loop.run_in_executor(None, fetch_eth_balance, wallet_address)
    usdc_balance = await loop.run_in_executor(None, fetch_usdc_balance, wallet_address)
    st = load_trading_state()
    coingecko_price = await loop.run_in_executor(None, fetch_eth_price)
    pyth_price = await loop.run_in_executor(None, fetch_eth_price_pyth)
    if pyth_price == 0.0:
        pyth_price = coingecko_price
    prices_list = [item["price"] for item in st.get("price_history", [])]
    num_prices = len(prices_list)
    sma_5 = sum(prices_list[-5:]) / min(5, num_prices) if num_prices > 0 else coingecko_price
    if coingecko_price > sma_5 * 1.002:
        trend = "alta"
    elif coingecko_price < sma_5 * 0.998:
        trend = "queda"
    else:
        trend = "lateral"
    return {
        "status": "ativo" if agent_initialized else "erro",
        "network": network_id,
        "address": wallet_address,
        "balance": f"{eth_balance:.5f}",
        "usdc_balance": f"{usdc_balance:.2f}",
        "average_buy_price": f"{st.get('average_buy_price', 0.0):.2f}",
        "total_trades": st.get("total_trades", 0),
        "autonomous_active": is_autonomous_running,
        "interval": trading_interval_seconds,
        "trades_history": st.get("trades_history", []),
        "coingecko_price": f"{coingecko_price:.2f}",
        "pyth_price": f"{pyth_price:.2f}",
        "trend": trend,
        "price_history": st.get("price_history", [])
    }


async def _build_futures_summary() -> dict:
    """Builds a compact futures payload (positions + unrealized_pnl) for the WS broadcast."""
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
    st = load_trading_state()
    mids = hl_mids_cache

    if dry_run:
        positions = st.get("simulated_hyperliquid_positions", {})
        total_pnl = 0.0
        active_list = []
        for coin, pos in positions.items():
            entry = pos["entryPx"]
            sz = pos["szi"]
            side = pos["side"]
            mid_px = float(mids.get(coin, entry))
            pnl = (mid_px - entry) * sz if side == "LONG" else (entry - mid_px) * sz
            total_pnl += pnl
            active_list.append({
                "coin": coin,
                "side": side,
                "szi": sz,
                "entryPx": entry,
                "markPx": mid_px,
                "leverage": pos.get("leverage", 1),
                "unrealizedPnl": round(pnl, 2),
                "marginUsed": pos.get("marginUsed", 0),
            })
        return {"positions": active_list, "unrealized_pnl": f"{total_pnl:.2f}"}
    else:
        if not wallet_provider:
            return {"positions": [], "unrealized_pnl": "0.00"}
        try:
            loop = asyncio.get_event_loop()
            def _get_user_state():
                from hyperliquid.info import Info
                from hyperliquid.utils import constants
                info = Info(constants.TESTNET_API_URL, skip_ws=True)
                return info.user_state(wallet_provider.get_address())
            user_state = await loop.run_in_executor(None, _get_user_state)
            total_pnl = 0.0
            active_list = []
            for pos_wrapper in user_state.get("assetPositions", []):
                p = pos_wrapper.get("position", {})
                coin = p.get("coin")
                szi = float(p.get("szi", 0.0))
                if szi != 0.0:
                    pnl = float(p.get("unrealizedPnl", 0.0))
                    total_pnl += pnl
                    active_list.append({
                        "coin": coin,
                        "side": "LONG" if szi > 0 else "SHORT",
                        "szi": abs(szi),
                        "entryPx": float(p.get("entryPx", 0.0)),
                        "markPx": float(mids.get(coin, p.get("entryPx", 0.0))),
                        "leverage": p.get("leverage", {}).get("value", 1),
                        "unrealizedPnl": round(pnl, 2),
                        "marginUsed": round(float(p.get("marginUsed", 0.0)), 2),
                    })
            return {"positions": active_list, "unrealized_pnl": f"{total_pnl:.2f}"}
        except Exception:
            return {"positions": [], "unrealized_pnl": "0.00"}


async def ws_broadcast_loop():
    """Background loop: pushes updates to all connected WS clients.

    Runs on two triggers:
    - A new log arrives (immediate push via _broadcast_trigger queue)
    - Every 10 s unconditionally (heartbeat / price refresh)
    """
    HEARTBEAT = 10.0
    trigger = _get_broadcast_trigger()

    while True:
        try:
            # Wait up to HEARTBEAT seconds for a trigger signal without using wait_for (Python 3.14 compatibility)
            last_log = None
            for _ in range(int(HEARTBEAT)):
                if not trigger.empty():
                    last_log = trigger.get_nowait()
                    break
                await asyncio.sleep(1.0)
            
            if last_log is None:
                last_log = agent_logs[-1] if agent_logs else None

            if not ws_manager._connections:
                continue

            status_payload = await _build_status_payload()
            futures_summary = await _build_futures_summary()

            await ws_manager.broadcast({
                "type": "update",
                "data": {
                    "status": status_payload,
                    "futures": futures_summary,
                    "last_log": last_log,
                }
            })
        except Exception as e:
            logger.error(f"Erro no loop de broadcast WebSocket: {e}")


async def sltp_monitoring_loop():
    """
    Loop em background que monitora os preços dos ativos com posições em aberto
    e executa fechamento automático caso os limites de Stop Loss (SL) ou Take Profit (TP) sejam atingidos.
    """
    add_log("Loop de monitoramento de SL/TP de futuros iniciado.", "system")
    while True:
        try:
            state = load_trading_state()
            targets = state.get("futures_sl_tp_targets", {})

            if targets:
                mids = hl_mids_cache

                active_targets = list(targets.keys())
                for asset in active_targets:
                    target_info = targets[asset]
                    sl = target_info.get("sl")
                    tp = target_info.get("tp")
                    direction = target_info.get("direction", "LONG")

                    if asset not in mids:
                        continue

                    current_price = float(mids[asset])
                    trigger_close = False
                    reason = ""

                    if direction == "LONG":
                        if sl and current_price <= sl:
                            trigger_close = True
                            reason = f"Stop Loss atingido (${current_price:.2f} <= ${sl:.2f})"
                        elif tp and current_price >= tp:
                            trigger_close = True
                            reason = f"Take Profit atingido (${current_price:.2f} >= ${tp:.2f})"
                    elif direction == "SHORT":
                        if sl and current_price >= sl:
                            trigger_close = True
                            reason = f"Stop Loss atingido (${current_price:.2f} >= ${sl:.2f})"
                        elif tp and current_price <= tp:
                            trigger_close = True
                            reason = f"Take Profit atingido (${current_price:.2f} <= ${tp:.2f})"

                    if trigger_close:
                        add_log(f"[SL/TP] Disparando fechamento automático para {asset}-PERP: {reason}", "warning")
                        if agent_initialized and trading_agent._close_position_func:
                            try:
                                if hasattr(trading_agent._close_position_func, "invoke"):
                                    result = trading_agent._close_position_func.invoke({"asset": asset})
                                else:
                                    result = trading_agent._close_position_func(asset)
                                add_log(f"[SL/TP] Fechamento de {asset}-PERP executado. Detalhes: {result}", "system")
                            except Exception as e:
                                logger.error(f"Erro ao executar fechamento automático de {asset}: {e}")
                                add_log(f"[SL/TP] Falha ao fechar {asset}-PERP: {e}", "error")

        except Exception as e:
            logger.error(f"Erro no loop de monitoramento de SL/TP: {e}")

        await asyncio.sleep(10)

@app.on_event("startup")
async def startup_event():
    """Inicializa as tarefas em background na inicialização do servidor."""
    global hl_info_ws
    try:
        from hyperliquid.info import Info
        from hyperliquid.utils import constants
        hl_info_ws = Info(constants.TESTNET_API_URL, skip_ws=False)
        hl_info_ws.subscribe({"type": "allMids"}, on_all_mids)
        logger.info("Inscrito no WebSocket nativo da Hyperliquid (allMids)")
    except Exception as e:
        logger.error(f"Erro ao iniciar WS da Hyperliquid: {e}")

    asyncio.create_task(sltp_monitoring_loop())
    asyncio.create_task(ws_broadcast_loop())

def get_indicators_for_prompt(asset: str) -> str:
    """Calcula indicadores técnicos (RSI, Bollinger Bands, MACD) de forma local/síncrona para injetar no prompt."""
    try:
        from hyperliquid.info import Info
        from hyperliquid.utils import constants
        import pandas as pd
        import time

        info = Info(constants.TESTNET_API_URL, skip_ws=True)
        end_time = int(time.time() * 1000)
        # 100 velas de 5m
        start_time = end_time - 100 * 60 * 1000 * 5
        
        candles = info.candles_snapshot(asset.upper(), "5m", start_time, end_time)
        if not candles:
            return f"Não foi possível obter velas para {asset}."
            
        df_data = []
        for c in candles:
            df_data.append({
                "time": c["t"],
                "open": float(c["o"]),
                "high": float(c["h"]),
                "low": float(c["l"]),
                "close": float(c["c"]),
                "volume": float(c["v"])
            })
            
        df = pd.DataFrame(df_data)
        df = df.sort_values("time").reset_index(drop=True)
        
        df["sma_5"] = df["close"].rolling(window=5).mean()
        df["sma_20"] = df["close"].rolling(window=20).mean()
        
        df["std_20"] = df["close"].rolling(window=20).std()
        df["bb_upper"] = df["sma_20"] + (2 * df["std_20"])
        df["bb_lower"] = df["sma_20"] - (2 * df["std_20"])
        
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        loss = loss.replace(0, 1e-9)
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))
        
        df["ema_12"] = df["close"].ewm(span=12, adjust=False).mean()
        df["ema_26"] = df["close"].ewm(span=26, adjust=False).mean()
        df["macd"] = df["ema_12"] - df["ema_26"]
        df["signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["hist"] = df["macd"] - df["signal"]
        
        latest = df.iloc[-1]
        
        return (
            f"Preço: ${latest['close']:.2f}\n"
            f"- RSI (14): {latest['rsi']:.2f}\n"
            f"- Bollinger Bands (20, 2): Superior ${latest['bb_upper']:.2f} | Média ${latest['sma_20']:.2f} | Inferior ${latest['bb_lower']:.2f}\n"
            f"- MACD (12, 26, 9): Valor {latest['macd']:.4f} | Sinal {latest['signal']:.4f} | Histograma {latest['hist']:.4f}"
        )
    except Exception as e:
        logger.error(f"Erro local ao calcular indicadores para {asset}: {e}")
        return f"Erro ao calcular indicadores locais: {str(e)}"

async def autonomous_trading_loop():
    """
    Loop periódico que roda em background executando análises de mercado
    e permitindo que o agente decida de forma autônoma se realiza swaps ou não.
    """
    global is_autonomous_running
    add_log("Loop autônomo de trading iniciado.", "system")

    while is_autonomous_running:
        try:
            if not agent:
                add_log("Agente não inicializado. Abortando loop de trading.", "error")
                is_autonomous_running = False
                break

            eth_price = fetch_eth_price()
            add_log(f"Iniciando análise autônoma do mercado. Preço atual do ETH: ${eth_price:.2f} USD", "market")

            eth_before = fetch_eth_balance(wallet_address)
            usdc_before = fetch_usdc_balance(wallet_address)
            add_log(f"Saldos antes da decisão: {eth_before:.5f} ETH / {usdc_before:.2f} USDC", "wallet")

            state = load_trading_state()

            hl_status = "Sem informações de futuros disponíveis no momento."
            if agent_initialized and trading_agent._get_positions_func:
                try:
                    if hasattr(trading_agent._get_positions_func, "invoke"):
                        hl_status = trading_agent._get_positions_func.invoke({})
                    else:
                        hl_status = trading_agent._get_positions_func()
                except Exception as e:
                    logger.error(f"Erro ao obter posições da Hyperliquid para o loop: {e}")

            # Calcular indicadores técnicos no servidor para evitar que o agente gaste chamadas de LLM (API Quota)
            loop = asyncio.get_event_loop()
            eth_indicators = await loop.run_in_executor(None, get_indicators_for_prompt, "ETH")
            btc_indicators = await loop.run_in_executor(None, get_indicators_for_prompt, "BTC")

            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            state["price_history"].append({"timestamp": timestamp, "price": eth_price})
            if len(state["price_history"]) > 20:
                state["price_history"].pop(0)
            save_trading_state(state)

            prices_list = [item["price"] for item in state["price_history"]]
            num_prices = len(prices_list)

            if num_prices > 0:
                sma_5 = sum(prices_list[-5:]) / min(5, num_prices)
                if num_prices >= 5:
                    variation = ((eth_price - prices_list[-5]) / prices_list[-5]) * 100.0
                else:
                    variation = 0.0
            else:
                sma_5 = eth_price
                variation = 0.0

            if eth_price > sma_5 * 1.002:
                trend = "Em alta (Bullish)"
            elif eth_price < sma_5 * 0.998:
                trend = "Em queda (Bearish)"
            else:
                trend = "Lateral (Sideways)"

            recent_prices_str = ", ".join([f"${p:.2f}" for p in prices_list[-5:]])
            avg_buy = state.get("average_buy_price", 0.0)
            undistributed_profit = state.get("undistributed_profit", 0.0)

            prompt = (
                f"Análise de mercado autônoma em tempo real.\n"
                f"- Preço de referência ETH/USD atual: ${eth_price:.2f}\n"
                f"- Preços recentes: [{recent_prices_str}]\n"
                f"- Média Móvel (SMA-5): ${sma_5:.2f} USD\n"
                f"- Tendência de Curto Prazo: {trend} (Variação: {variation:+.2f}%)\n"
                f"- Seu preço médio de compra spot (average cost): ${avg_buy:.2f} USD\n"
                f"- Seu lucro não distribuído acumulado: ${undistributed_profit:.2f} USD\n"
                f"- Seu saldo spot atual na Base: {eth_before:.6f} ETH e {usdc_before:.2f} USDC\n"
                f"- Seu status de futuros na Hyperliquid:\n{hl_status}\n\n"
                f"INDICADORES TÉCNICOS JÁ PRE-CALCULADOS (Use esses dados em vez de chamar ferramentas de cálculo):\n"
                f"=== ETH-PERP ===\n{eth_indicators}\n\n"
                f"=== BTC-PERP ===\n{btc_indicators}\n\n"
                f"Diretrizes de Decisão Inteligente:\n"
                f"1. **REGRA DE SWEEP (Regra 10 - Lucro de 200 dólares)**:\n"
                f"   - Se o seu lucro acumulado ('undistributed_profit') for igual ou superior a $200, você DEVE priorizar a transferência de $200 de lucro usando a ferramenta 'withdraw_profit_to_owner' para a carteira `0x1d68FD5064AE7820E4597641FeCC94B9C47cF217`.\n"
                f"2. **TRADING SPOT (Base)**:\n"
                f"   - COMPRA (Swap USDC -> ETH): Se tiver USDC disponível (>0.01 USDC) e o preço estiver abaixo do seu preço médio de compra (ou se preço médio for 0.00).\n"
                f"   - VENDA (Swap ETH -> USDC): Se o preço atual for pelo menos 1% superior ao seu preço médio de compra (${avg_buy:.2f}), e seu saldo de ETH for maior que o limite de segurança (0.0005 ETH).\n"
                f"3. **TRADING DE FUTUROS (Hyperliquid)**:\n"
                f"   - Você possui indicadores técnicos de ETH e BTC pré-calculados acima. Se não tiver nenhuma posição de futuros aberta, você pode abrir uma nova posição de futuros em 'ETH' ou 'BTC'.\n"
                f"   - LONG (open_hyperliquid_position): Se o RSI estiver em sobrevenda extrema (<35) e o MACD Histograma for positivo ou cruzando para cima. Considere também se o preço está próximo à Banda de Bollinger Inferior. Defina alavancagem de 3x a 5x isolado, com Stop Loss em 5% e Take Profit em 10% (sl_percent=5.0, tp_percent=10.0).\n"
                f"   - SHORT (open_hyperliquid_position): Se o RSI estiver em sobrecompra extrema (>65) e o MACD Histograma for negativo ou cruzando para baixo. Considere também se o preço está próximo à Banda de Bollinger Superior. Defina alavancagem de 3x a 5x isolado, com Stop Loss em 5% e Take Profit em 10% (sl_percent=5.0, tp_percent=10.0).\n"
                f"   - FECHAMENTO ANTECIPADO: Se você tiver uma posição ativa e os indicadores indicarem exaustão extrema (ex: RSI > 75 ou MACD divergente para LONG ativo, ou RSI < 25 para SHORT ativo), use 'close_hyperliquid_position' para fechar e garantir lucro.\n"
                f"4. **PRESERVAR GÁS**: Nunca faça swaps de spot que reduzam seu saldo de ETH abaixo de 0.0005 ETH.\n"
                f"5. **ECONOMIA DE REQUESTS (MANDATÓRIO)**: Para evitar limite de requisições da API Gemini, NÃO use 'calculate_technical_indicators' nem outras ferramentas de consulta caso os dados fornecidos acima já sejam suficientes. Vá direto para a decisão de HOLD ou execute a transação usando 'open_hyperliquid_position' ou 'close_hyperliquid_position'.\n"
                f"6. **HOLD (AGUARDAR)**: Se não houver oportunidade clara de trading spot/futuros, decida por APENAS AGUARDAR. Explique de forma analítica com base na tendência e indicadores fornecidos.\n\n"
                f"Se decidir realizar uma transação, execute-a agora usando suas ferramentas. Dê sua resposta final em português explicando sua tese de trading de forma técnica."
            )

            # Executa com limite de recursão para evitar loops infinitos da LLM e estouro de cota
            response = await agent.ainvoke({"messages": [("user", prompt)]}, config={"recursion_limit": 10})

            messages = response.get("messages", [])
            if messages:
                agent_reply = messages[-1].content
                add_log(f"Decisão do Agente: {agent_reply}", "agent")
            else:
                add_log("Agente analisou o mercado, mas não retornou nenhuma mensagem.", "warning")

            await asyncio.sleep(5)

            eth_after = fetch_eth_balance(wallet_address)
            usdc_after = fetch_usdc_balance(wallet_address)
            record_trade_deltas(eth_before, usdc_before, eth_after, usdc_after)

        except Exception as e:
            add_log(f"Erro na execução do loop de trading: {e}", "error")

        await asyncio.sleep(trading_interval_seconds)

# --- Métricas de Desempenho & Benchmarks ---

_historical_prices_cache = {
    "data": None,
    "last_fetched": None
}

def fetch_cryptocompare_history() -> List[Dict[str, Any]]:
    """Busca o histórico de preços diários do ETH em USD usando a CryptoCompare com cache de 1 hora."""
    now = datetime.datetime.now()
    cache = _historical_prices_cache
    if cache["data"] and cache["last_fetched"] and (now - cache["last_fetched"]).total_seconds() < 3600:
        return cache["data"]

    url = "https://min-api.cryptocompare.com/data/v2/histoday?fsym=ETH&tsym=USD&limit=90"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('Response') == 'Success':
                raw_data = data.get('Data', {}).get('Data', [])
                prices = [{'time': x['time'], 'close': float(x['close'])} for x in raw_data]
                cache["data"] = prices
                cache["last_fetched"] = now
                return prices
    except Exception as e:
        logger.error(f"Erro ao buscar histórico de preços da CryptoCompare: {e}")
    return cache["data"] or []

@app.get("/api/performance")
async def get_performance():
    """Calcula a performance do agente e benchmarks para várias janelas temporais."""
    prices = fetch_cryptocompare_history()
    if not prices:
        raise HTTPException(status_code=500, detail="Não foi possível obter o histórico de preços do oráculo.")

    current_price = fetch_eth_price()
    if current_price <= 0.0:
        current_price = prices[-1]['close']

    state = load_trading_state()
    actual_trades = state.get("trades_history", [])

    current_eth = float(state.get("simulated_eth_balance", 0.05))
    current_usdc = float(state.get("simulated_usdc_balance", 100.0))
    current_portfolio_value = current_usdc + (current_eth * current_price)

    windows = {
        '24h': 1,
        '48h': 2,
        '7d': 7,
        '14d': 14,
        '30d': 30,
        '60d': 60,
        '90d': 90
    }

    performance_results = {}
    current_time = datetime.datetime.now()

    for label, days in windows.items():
        idx = -days - 1
        if len(prices) >= abs(idx):
            start_price = prices[idx]['close']
        else:
            start_price = prices[0]['close']

        bh_return = ((current_price - start_price) / start_price) * 100

        dca_usd_spent = 0.0
        dca_eth_accumulated = 0.0

        relevant_prices = prices[-days-1:-1] if days < len(prices) else prices[:-1]
        for p in relevant_prices:
            close_p = p['close']
            dca_usd_spent += 1.0
            dca_eth_accumulated += (1.0 / close_p)

        dca_final_value = dca_eth_accumulated * current_price
        dca_pnl_usd = dca_final_value - dca_usd_spent
        dca_return = (dca_pnl_usd / dca_usd_spent) * 100 if dca_usd_spent > 0 else 0.0

        start_datetime = current_time - datetime.timedelta(days=days)
        window_trades = []
        for t in actual_trades:
            try:
                t_time = datetime.datetime.strptime(t['timestamp'], "%Y-%m-%d %H:%M:%S")
                if t_time >= start_datetime:
                    window_trades.append(t)
            except Exception:
                pass

        start_eth = current_eth
        start_usdc = current_usdc
        for t in window_trades:
            if t['type'] == 'BUY':
                start_eth -= t.get('eth_amount', 0.0)
                start_usdc += t.get('usdc_amount', 0.0)
            elif t['type'] == 'SELL':
                start_eth += t.get('eth_amount', 0.0)
                start_usdc -= t.get('usdc_amount', 0.0)

        start_portfolio_value = start_usdc + (start_eth * start_price)
        agent_pnl_usd = current_portfolio_value - start_portfolio_value
        agent_return = (agent_pnl_usd / start_portfolio_value) * 100 if start_portfolio_value > 0 else 0.0

        performance_results[label] = {
            "days": days,
            "start_date": start_datetime.strftime("%Y-%m-%d"),
            "start_price": start_price,
            "current_price": current_price,
            "bh_return": bh_return,
            "dca_spent": dca_usd_spent,
            "dca_pnl_usd": dca_pnl_usd,
            "dca_return": dca_return,
            "agent_trades": len(window_trades),
            "agent_start_eth": start_eth,
            "agent_start_usdc": start_usdc,
            "agent_start_value": start_portfolio_value,
            "agent_pnl_usd": agent_pnl_usd,
            "agent_return": agent_return
        }

    return {
        "current_time": current_time.strftime("%Y-%m-%d %H:%M:%S"),
        "current_price": current_price,
        "current_portfolio_value": current_portfolio_value,
        "performance": performance_results
    }

# --- Endpoints da API REST ---

class ChatMessage(BaseModel):
    message: str

class CloseManualRequest(BaseModel):
    asset: str

@app.get("/api/status")
async def get_status():
    """Retorna o status atual do agente, rede, endereço e saldo."""
    if not wallet_provider:
        return {
            "status": "inativo",
            "network": network_id,
            "address": "Não inicializado",
            "balance": "0.00",
            "usdc_balance": "0.00",
            "average_buy_price": "0.00",
            "total_trades": 0,
            "autonomous_active": False,
            "trades_history": [],
            "coingecko_price": "0.00",
            "pyth_price": "0.00",
            "trend": "lateral",
            "price_history": []
        }

    eth_balance = fetch_eth_balance(wallet_address)
    usdc_balance = fetch_usdc_balance(wallet_address)
    state = load_trading_state()

    coingecko_price = fetch_eth_price()
    pyth_price = fetch_eth_price_pyth()
    if pyth_price == 0.0:
        pyth_price = coingecko_price

    prices_list = [item["price"] for item in state.get("price_history", [])]
    num_prices = len(prices_list)

    if num_prices > 0:
        sma_5 = sum(prices_list[-5:]) / min(5, num_prices)
    else:
        sma_5 = coingecko_price

    if coingecko_price > sma_5 * 1.002:
        trend = "alta"
    elif coingecko_price < sma_5 * 0.998:
        trend = "queda"
    else:
        trend = "lateral"

    return {
        "status": "ativo" if agent_initialized else "erro",
        "network": network_id,
        "address": wallet_address,
        "balance": f"{eth_balance:.5f}",
        "usdc_balance": f"{usdc_balance:.2f}",
        "average_buy_price": f"{state.get('average_buy_price', 0.0):.2f}",
        "total_trades": state.get("total_trades", 0),
        "autonomous_active": is_autonomous_running,
        "interval": trading_interval_seconds,
        "trades_history": state.get("trades_history", []),
        "coingecko_price": f"{coingecko_price:.2f}",
        "pyth_price": f"{pyth_price:.2f}",
        "trend": trend,
        "price_history": state.get("price_history", [])
    }

@app.get("/api/logs")
async def get_logs():
    """Retorna os logs em memória."""
    return {"logs": agent_logs}

@app.get("/api/futures/state")
async def get_futures_state():
    """Retorna o estado detalhado da conta e posições de futuros perpétuos da Hyperliquid (real ou simulado)."""
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
    state = load_trading_state()
    targets = state.get("futures_sl_tp_targets", {})
    history = state.get("futures_trades_history", [])

    mids = {}
    try:
        from hyperliquid.info import Info
        from hyperliquid.utils import constants
        info = Info(constants.TESTNET_API_URL, skip_ws=True)
        mids = info.all_mids()
    except Exception as e:
        logger.error(f"Erro ao obter mids da Hyperliquid para o estado de futuros: {e}")

    if dry_run:
        positions = state.get("simulated_hyperliquid_positions", {})
        total_pnl = 0.0
        active_positions_list = []

        for coin, pos in list(positions.items()):
            entry = pos["entryPx"]
            sz = pos["szi"]
            side = pos["side"]
            margin = pos["marginUsed"]
            leverage = pos["leverage"]

            mid_px = float(mids.get(coin, entry))

            if side == "LONG":
                pnl = (mid_px - entry) * sz
            else:
                pnl = (entry - mid_px) * sz

            pos["unrealizedPnl"] = round(pnl, 4)
            total_pnl += pnl

            target = targets.get(coin, {})
            active_positions_list.append({
                "coin": coin,
                "side": side,
                "szi": sz,
                "entryPx": entry,
                "markPx": mid_px,
                "leverage": leverage,
                "unrealizedPnl": round(pnl, 2),
                "marginUsed": margin,
                "sl": target.get("sl"),
                "tp": target.get("tp")
            })

        save_trading_state(state)

        sim_balance = float(state.get("simulated_hyperliquid_balance", 1000.0))
        account_value = sim_balance + sum(pos["marginUsed"] for pos in positions.values()) + total_pnl

        return {
            "account_value": f"{account_value:.2f}",
            "available_margin": f"{sim_balance:.2f}",
            "position_margin": f"{sum(pos['marginUsed'] for pos in positions.values()):.2f}",
            "unrealized_pnl": f"{total_pnl:.2f}",
            "positions": active_positions_list,
            "targets": targets,
            "trades_history": history,
            "is_dry_run": True
        }
    else:
        if not wallet_provider:
            raise HTTPException(status_code=500, detail="Provedor de carteira não inicializado.")

        try:
            from hyperliquid.info import Info
            from hyperliquid.utils import constants
            info = Info(constants.TESTNET_API_URL, skip_ws=True)
            address = wallet_provider.get_address()
            user_state = info.user_state(address)

            margin = user_state.get("marginSummary", {})
            account_value = float(margin.get("accountValue", 0.0))
            available = float(user_state.get("withdrawable", 0.0))

            active_positions_list = []
            total_margin_used = 0.0
            total_pnl = 0.0

            for pos_wrapper in user_state.get("assetPositions", []):
                p = pos_wrapper.get("position", {})
                coin = p.get("coin")
                szi = float(p.get("szi", 0.0))

                if szi != 0.0:
                    entry = float(p.get("entryPx", 0.0))
                    pnl = float(p.get("unrealizedPnl", 0.0))
                    side = "LONG" if szi > 0 else "SHORT"
                    lev = p.get("leverage", {}).get("value", 1)
                    margin_used = float(p.get("marginUsed", 0.0))

                    total_margin_used += margin_used
                    total_pnl += pnl

                    mid_px = float(mids.get(coin, entry))
                    target = targets.get(coin, {})

                    active_positions_list.append({
                        "coin": coin,
                        "side": side,
                        "szi": abs(szi),
                        "entryPx": entry,
                        "markPx": mid_px,
                        "leverage": lev,
                        "unrealizedPnl": round(pnl, 2),
                        "marginUsed": round(margin_used, 2),
                        "sl": target.get("sl"),
                        "tp": target.get("tp")
                    })

            active_coins = {pos["coin"] for pos in active_positions_list}
            modified = False
            for coin in list(targets.keys()):
                if coin not in active_coins:
                    del targets[coin]
                    modified = True
            if modified:
                state["futures_sl_tp_targets"] = targets
                save_trading_state(state)

            return {
                "account_value": f"{account_value:.2f}",
                "available_margin": f"{available:.2f}",
                "position_margin": f"{total_margin_used:.2f}",
                "unrealized_pnl": f"{total_pnl:.2f}",
                "positions": active_positions_list,
                "targets": targets,
                "trades_history": history,
                "is_dry_run": False
            }
        except Exception as e:
            logger.error(f"Erro ao obter dados reais de futuros da Hyperliquid: {e}")
            raise HTTPException(status_code=500, detail=f"Erro ao obter dados de futuros: {str(e)}")

@app.post("/api/futures/close_manual")
async def close_manual(payload: CloseManualRequest):
    """Encerra manualmente uma posição de futuros perpétuos ativa na Hyperliquid."""
    if not agent_initialized or not trading_agent._close_position_func:
        raise HTTPException(status_code=500, detail="Agente ou ferramenta de encerramento não inicializado.")

    asset = payload.asset.upper()
    add_log(f"Usuário solicitou fechamento manual da posição em {asset}-PERP.", "user")

    try:
        if hasattr(trading_agent._close_position_func, "invoke"):
            result = trading_agent._close_position_func.invoke({"asset": asset})
        else:
            result = trading_agent._close_position_func(asset)
        add_log(f"Resultado do fechamento manual de {asset}: {result}", "system")
        return {"status": "success", "message": result}
    except Exception as e:
        logger.error(f"Erro ao fechar posição de {asset}: {e}")
        add_log(f"Falha no fechamento manual de {asset}-PERP: {e}", "error")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def post_chat(payload: ChatMessage):
    """Envia uma mensagem direta de chat para o agente e retorna a resposta."""
    if not agent:
        raise HTTPException(status_code=500, detail="Agente de trading não inicializado. Configure a chave OPENAI_API_KEY no seu arquivo .env.")

    global chat_history
    user_msg = payload.message
    add_log(f"Usuário enviou mensagem: {user_msg}", "user")

    eth_before = fetch_eth_balance(wallet_address)
    usdc_before = fetch_usdc_balance(wallet_address)

    try:
        chat_history.append(("user", user_msg))
        history_snapshot = list(chat_history)

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, lambda: agent.invoke({"messages": history_snapshot})
        )
        messages = response.get("messages", [])

        await asyncio.sleep(5)

        eth_after = fetch_eth_balance(wallet_address)
        usdc_after = fetch_usdc_balance(wallet_address)
        record_trade_deltas(eth_before, usdc_before, eth_after, usdc_after)

        if messages:
            agent_reply = messages[-1].content
            add_log(f"Resposta do Agente: {agent_reply}", "agent")
            chat_history.append(("assistant", agent_reply))
            return {"reply": agent_reply}
        else:
            return {"reply": "Não consegui processar a resposta."}
    except Exception as e:
        add_log(f"Erro ao processar chat: {e}", "error")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chat/history")
async def get_chat_history():
    """Retorna o histórico de chat para carregar no frontend."""
    return {"history": [{"role": r, "content": c} for r, c in chat_history]}

@app.delete("/api/chat/history")
async def clear_chat_history():
    """Limpa o histórico de conversa."""
    global chat_history
    chat_history = []
    return {"ok": True}

@app.post("/api/toggle")
async def toggle_autonomous(background_tasks: BackgroundTasks):
    """Ativa ou desativa o loop autônomo de trading."""
    global is_autonomous_running

    if not agent_initialized:
        raise HTTPException(status_code=400, detail="Agente não está inicializado devido a erro de configuração.")

    if is_autonomous_running:
        is_autonomous_running = False
        add_log("Parando loop autônomo de trading...", "system")
        return {"active": False, "message": "Trading autônomo desativado."}
    else:
        is_autonomous_running = True
        background_tasks.add_task(autonomous_trading_loop)
        return {"active": True, "message": "Trading autônomo ativado com sucesso!"}


# ─── WebSocket endpoint ───────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        # Send current state immediately on connect
        status_payload = await _build_status_payload()
        futures_summary = await _build_futures_summary()
        last_log = agent_logs[-1] if agent_logs else None
        await websocket.send_json({
            "type": "update",
            "data": {
                "status": status_payload,
                "futures": futures_summary,
                "last_log": last_log,
            }
        })
        # Keep alive — the client may send pings; we ignore any messages
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


# --- Interface Web ---

os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)
os.makedirs("templates", exist_ok=True)

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Retorna o index.html principal do Dashboard."""
    if os.path.exists("templates/index.html"):
        with open("templates/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    return HTMLResponse(content="<h1>Dashboard index.html não encontrado no diretório templates/</h1>", status_code=404)

@app.get("/static/css/style.css")
async def get_css():
    """Retorna o arquivo de estilo CSS."""
    if os.path.exists("static/css/style.css"):
        with open("static/css/style.css", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200, media_type="text/css")
    return HTMLResponse(content="CSS não encontrado", status_code=404)

@app.get("/static/js/app.js")
async def get_js():
    """Retorna o arquivo JavaScript."""
    if os.path.exists("static/js/app.js"):
        with open("static/js/app.js", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200, media_type="application/javascript")
    return HTMLResponse(content="JS não encontrado", status_code=404)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    logger.info(f"Iniciando o servidor FastAPI em http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)
