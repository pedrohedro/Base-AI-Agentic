# Manual: Como Claude Code Opera como Cérebro de Trading via MCP

**Projeto:** Base AI Agentic  
**Repositório:** `github.com/pedrohedro/Base-AI-Agentic`  
**Data:** 2026-05-26

---

## Visão Geral

Este manual descreve como qualquer instância do **Claude Code** pode se conectar ao agente de trading deste projeto via MCP (Model Context Protocol) e atuar como cérebro de decisão — consumindo dados reais de mercado do `agentic.market` e executando operações na Hyperliquid testnet.

```
Claude Code  ←→  MCP Server (mcp_server.py)  ←→  FastAPI Backend (main.py)
                        ↕                               ↕
              agentic.market (Pyth, Seerium)    Hyperliquid + Base L2
```

---

## 1. Pré-requisitos

### Sistema
- Python 3.10+
- macOS / Linux

### Variáveis de ambiente obrigatórias no `.env`
```env
# Chaves da Coinbase Developer Platform (obrigatório para carteira)
CDP_API_KEY_ID="organizations/..."
CDP_API_KEY_SECRET="-----BEGIN EC PRIVATE KEY-----\n..."

# Configuração da blockchain
NETWORK_ID="base-mainnet"   # ou "base-sepolia" para testes
DRY_RUN="true"              # true = simulação | false = execução real

# LLM provider (para o loop autônomo interno)
LLM_PROVIDER="claude"       # ou "openai" ou "gemini"
ANTHROPIC_API_KEY="sk-ant-..."
ANTHROPIC_MODEL="claude-haiku-4-5-20251001"
```

---

## 2. Instalação e inicialização do backend

```bash
# 1. Clonar o repositório
git clone git@github.com:pedrohedro/Base-AI-Agentic.git
cd Base-AI-Agentic

# 2. Criar e ativar o ambiente virtual
python3 -m venv venv
source venv/bin/activate

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com suas chaves

# 5. Iniciar o backend FastAPI
nohup venv/bin/python -m uvicorn main:app \
  --host 0.0.0.0 --port 8000 --loop asyncio \
  >> server.log 2>&1 &

# 6. Verificar se subiu corretamente
curl -s http://localhost:8000/api/status | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print(f'OK | ETH: {d[\"balance\"]}')"
```

---

## 3. Configuração do MCP no Claude Code

O arquivo `.mcp.json` na raiz do projeto já configura o servidor automaticamente:

```json
{
  "mcpServers": {
    "base-trading-agent": {
      "command": "venv/bin/python",
      "args": ["mcp_server.py"],
      "env": {}
    }
  }
}
```

Para ativar, **abra o Claude Code de dentro do diretório do projeto**:

```bash
cd ~/Base-AI-Agentic
claude
```

O Claude Code detecta o `.mcp.json`, inicia o `mcp_server.py` como processo filho e as ferramentas ficam disponíveis automaticamente.

### Ferramentas disponíveis via MCP

| Ferramenta | Categoria |
|---|---|
| `status` | Estado do agente |
| `futures_status` | Posições abertas |
| `get_logs` | Histórico de decisões |
| `toggle_autonomous` | Liga/desliga loop |
| `get_pyth_price` | agentic.market — preço real |
| `get_seerium_opportunities` | agentic.market — sinais |
| `audit_token_risk` | agentic.market — auditoria |
| `get_technical_indicators` | RSI / Bollinger / MACD |
| `open_position` | Executar trade |
| `close_position` | Fechar posição |

---

## 4. Processo obrigatório antes de qualquer trade

Claude **deve seguir este fluxo** em toda sessão de análise:

```
1. status()                          → verificar saldos e loop autônomo
2. futures_status()                  → checar se há posição aberta
3. get_pyth_price("ETH")            → preço spot em tempo real
4. get_technical_indicators("ETH")  → RSI-14, Bollinger Bands, MACD
5. get_seerium_opportunities()      → sinais do agentic.market
6. [DECISÃO] LONG / SHORT / HOLD
7. open_position(...) se operar     → executar com SL e TP
8. get_logs(5)                      → confirmar registro
```

### Regras de decisão

```
RSI > 70  → SHORT (sobrecompra)
RSI < 30  → LONG  (sobrevenda)
30–70     → HOLD  (neutro)

Preço acima da Banda Superior Bollinger → SHORT
Preço abaixo da Banda Inferior Bollinger → LONG

MACD Histograma > 0 → viés de ALTA (confirma LONG)
MACD Histograma < 0 → viés de BAIXA (confirma SHORT)
```

### Parâmetros padrão

```python
open_position(
    asset="ETH",
    direction="LONG",    # ou "SHORT"
    margin_amount=50.0,  # USDC
    leverage=3,          # 3x a 5x isolada
    sl_percent=5.0,      # Stop Loss 5%
    tp_percent=10.0,     # Take Profit 10%
)
```

### Restrições de segurança

- Nunca abrir posição se `futures_status()` mostrar posição ativa
- Nunca reduzir ETH abaixo de 0.0005 na carteira Base (reserva de gas)
- Confirmar com o usuário antes de mudar `DRY_RUN` para `false`
- Confirmar com o usuário antes de chamar `toggle_autonomous()`

---

## 5. Ferramentas do agentic.market — comportamento esperado

### `get_pyth_price(token)`
- Sempre retorna dados reais via Pyth Network Hermes API (gratuita)
- Tokens: `ETH`, `BTC`, `SOL`, `USDC`

### `get_seerium_opportunities()`
- Tenta `https://api.seerium.xyz/opportunities`
- **HTTP 200**: oportunidades reais
- **HTTP 402**: exige micropagamento x402 → retorna análise alternativa
- **Erro / 404**: API indisponível → retorna análise alternativa

### `audit_token_risk(token_address)`
- Tenta `https://svm402.com/audit?address=...`
- Mesmo comportamento: real se disponível, fallback se 402/erro

### `get_technical_indicators(asset)`
- 100 velas de 5 minutos reais da Hyperliquid testnet
- Calcula RSI-14, Bollinger Bands (20,2) e MACD (12,26,9) com pandas
- Inclui interpretação: `SOBRECOMPRA / SOBREVENDA / NEUTRO`

---

## 6. Modos de operação

| Modo | Configuração | Comportamento |
|---|---|---|
| Simulação | `DRY_RUN=true` | Trades locais, nenhum fundo movido |
| Testnet real | `DRY_RUN=false` + faucet HL | Ordens reais na Hyperliquid testnet |
| Mainnet | `DRY_RUN=false` + `base-mainnet` | Fundos reais — confirmar com usuário |

### Financiar conta testnet Hyperliquid
1. Abrir `https://app.hyperliquid-testnet.xyz/` no browser
2. Conectar MetaMask com a carteira do projeto
3. Clicar em "Deposit" → "Testnet Faucet" → $10.000 USDC testnet
4. Mudar `DRY_RUN="false"` no `.env` e reiniciar o backend

---

## 7. Diagnóstico rápido

```bash
# Backend não responde
curl -s http://localhost:8000/api/status
nohup venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 --loop asyncio >> server.log 2>&1 &

# Ver erros de inicialização
tail -50 server.log

# Testar MCP server manualmente
venv/bin/python mcp_server.py

# Fechar posição travada
venv/bin/python agent_cli.py close ETH
```

---

## 8. Arquitetura

```
Base-AI-Agentic/
├── main.py              # FastAPI backend — endpoints REST
├── trading_agent.py     # ReAct Agent + tools (Hyperliquid, Base, agentic.market)
├── mcp_server.py        # MCP Server — expõe ferramentas para Claude Code
├── agent_cli.py         # CLI de controle via terminal
├── .mcp.json            # Configuração MCP para Claude Code (auto-carregado)
├── CLAUDE.md            # Contexto automático para Claude Code
├── .env                 # Chaves e configurações (não commitado)
├── trading_state.json   # Estado persistido (saldos, trades, posições)
└── venv/                # Ambiente Python isolado
```

---

*Setup realizado em 2026-05-26 via Claude Code.*
