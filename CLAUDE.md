# Base AI Agentic — Contexto para Claude Code

## O que é este projeto

Agente autônomo de trading quantitativo que opera:
- **Swaps Spot** na rede Base L2 via Uniswap V3 (USDC ↔ ETH)
- **Futuros Perpétuos** na Hyperliquid testnet (LONG/SHORT com alavancagem 3x–5x)

Stack: Python 3.14 + FastAPI + LangChain/LangGraph ReAct Agent + Coinbase AgentKit SDK + Hyperliquid SDK

---

## Contexto da sessão de configuração (2026-05-25)

Nesta sessão foi feita toda a estrutura do projeto. Os pontos críticos:

### Estrutura de diretórios
O projeto estava com estrutura duplicada e confusa (pasta `Base-AI-Agentic\` com backslash e symlinks). Foi reorganizado — tudo está agora diretamente em `~/Base-AI-Agentic/` sem aninhamento.

### MCP Server (`mcp_server.py`)
Expandido de 5 para 9 ferramentas. **Claude é o cérebro de decisão** que consome dados do agentic.market via MCP e executa trades diretamente — sem depender do MockAgent ou de uma chave LLM externa.

Ferramentas disponíveis via MCP:
| Ferramenta | Descrição |
|---|---|
| `status()` | Carteira, saldos, loop autônomo |
| `futures_status()` | Posições abertas, PnL, SL/TP |
| `get_logs(limit)` | Histórico de decisões |
| `toggle_autonomous()` | Liga/desliga loop autônomo |
| `get_pyth_price(token)` | Preço real via Pyth Network (ETH/BTC/SOL/USDC) |
| `get_seerium_opportunities()` | Feed agentic.market — sinais de arbitragem e momentum |
| `audit_token_risk(address)` | Auditoria de token ERC-20 via svm402 (agentic.market) |
| `get_technical_indicators(asset)` | RSI-14, Bollinger Bands, MACD de 100 velas 5m reais |
| `open_position(...)` | Abre posição perpétua na Hyperliquid |
| `close_position(asset)` | Fecha posição aberta |

### Integração Claude como LLM provider
`trading_agent.py` foi modificado para aceitar `LLM_PROVIDER="claude"` com `langchain-anthropic`. Basta colocar `ANTHROPIC_API_KEY` no `.env` e o agente ReAct usa Claude como cérebro autônomo 24/7.

### Fix crítico: `or True` removido
As ferramentas `get_seerium_opportunities` e `audit_token_risk` tinham `if response.status_code == 402 or True:` hardcoded — isso forçava sempre o retorno de dados mock. **Removido.** Agora tentam a API real primeiro.

---

## Estado atual do sistema

### Carteira
- **Endereço**: `0xC5Afe3898aa4F7F5f60352dd02e2c86B2f1aafFC`
- **Rede**: `base-mainnet`
- **Saldo real**: ~0.094 ETH + ~6.45 USDC
- **Chave privada**: `wallet_data.txt` (confirmado — deriva o endereço acima)

### Configuração `.env`
- `DRY_RUN="true"` — simulação ativa, nenhum fundo real é movido
- `LLM_PROVIDER="claude"` — configurado, mas precisa da `ANTHROPIC_API_KEY` real
- `NETWORK_ID="base-mainnet"`

### Hyperliquid
- Código aponta para `constants.TESTNET_API_URL` em todas as chamadas
- Conta testnet existe mas com **$0 real** (faucet só via browser em `app.hyperliquid-testnet.xyz`)
- Margem **simulada**: ~$940 USDC (local, não on-chain)
- Posição atual: SHORT ETH-PERP @ ~$2.140, 3x, SL $2.247 / TP $1.926

### Backend
- Rodando com `nohup` — **pode estar parado** se o Mac reiniciou
- Para verificar: `curl -s http://localhost:8000/api/status`
- Para iniciar: `venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 --loop asyncio &`

---

## Como Claude deve operar neste projeto

Quando aberto neste diretório, o MCP `base-trading-agent` é carregado automaticamente. Claude **não deve usar Bash para chamar curl** — deve usar as ferramentas MCP diretamente.

### Processo de decisão obrigatório antes de qualquer trade

1. `status()` — verificar saldos e estado do loop
2. `get_pyth_price("ETH")` — preço spot tempo real
3. `get_technical_indicators("ETH")` — RSI, Bollinger, MACD
4. `get_seerium_opportunities()` — sinais do agentic.market
5. Analisar e decidir: LONG / SHORT / HOLD
6. Se operar: `open_position(...)` com SL e TP
7. `get_logs(5)` — confirmar registro

### Regras de trading
- **SHORT**: RSI > 70 ou preço acima da Banda Superior Bollinger
- **LONG**: RSI < 30 ou preço abaixo da Banda Inferior Bollinger
- **HOLD**: RSI 30–70 e preço dentro das bandas
- Margem padrão: $50 USDC | Alavancagem: 3x–5x isolada
- SL: 5% | TP: 10%
- Nunca abrir se já houver posição ativa
- Nunca reduzir ETH abaixo de 0.0005 (reserva de gas)

---

## Comandos úteis

```bash
# Verificar se o backend está rodando
curl -s http://localhost:8000/api/status | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'OK | ETH: {d[\"balance\"]} | Loop: {d[\"autonomous_active\"]}')"

# Iniciar backend (se parado)
nohup venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 --loop asyncio >> server.log 2>&1 &

# Ver logs do agente
venv/bin/python agent_cli.py logs --limit 20

# Verificar saldo na Hyperliquid testnet
venv/bin/python -c "
from hyperliquid.info import Info
from hyperliquid.utils import constants
info = Info(constants.TESTNET_API_URL, skip_ws=True)
state = info.user_state('0xC5Afe3898aa4F7F5f60352dd02e2c86B2f1aafFC')
print(state.get('marginSummary', {}))
"
```

---

## Pendências / Próximos passos

- [ ] Adicionar `ANTHROPIC_API_KEY` real no `.env` para ativar o cérebro Claude autônomo
- [ ] Fazer faucet manual em `app.hyperliquid-testnet.xyz` para obter USDC testnet real
- [ ] Após faucet: mudar `DRY_RUN="false"` para executar ordens reais na testnet
- [ ] Implementar pagamento x402 real (Seerium e svm402 retornam 404 — endpoints mudaram)
