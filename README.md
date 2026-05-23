# Base Agentic - Autonomous Trading & Perp Futures Agent

Base Agentic é um agente autônomo de trading quantitativo e arbitragem on-chain que opera Swaps Spot na rede **Base L2** (via Uniswap V3) e Contratos Perpétuos de Futuros na **L1 da Hyperliquid** (Testnet ou Mainnet), com suporte a múltiplos oráculos de preço (CoinGecko + Pyth Network Hermes) e inteligência analítica baseada em indicadores técnicos (RSI, Bollinger Bands, MACD).

O painel é desenhado com uma estética neon premium dark e dividida em abas (Spot / Futuros), trazendo logs de decisão em tempo real, monitoramento ativo de Stop Loss (SL) e Take Profit (TP), e um mecanismo automatizado de transferência de lucros (Profit Sweep).

---

## 🏗️ Arquitetura do Sistema

A stack é dividida em 4 camadas fundamentais:

```
┌─────────────────────────────────────────────┐
│          AGENTIC.MARKET (Discovery)          │  -> Busca semântica de APIs premium
│    Marketplace de serviços x402              │     (Oráculos de sentimento, auditoria)
├─────────────────────────────────────────────┤
│          AGENTIC WALLETS (Custody)           │  -> Carteira local auto-custodial
│    Carteiras MPC ou chaves locais            │     (wallet_data.txt + session limits)
├─────────────────────────────────────────────┤
│          AGENTKIT (Framework)                │  -> SDK da Coinbase integrado com
│    SDK open-source com skills prontas        │     LangChain / LangGraph ReAct Agent
├─────────────────────────────────────────────┤
│          x402 PROTOCOL (Payments)            │  -> Micropayments automáticos via
│    HTTP 402 + USDC na Base                   │     código HTTP 402 Payment Required
└─────────────────────────────────────────────┘
```

---

## ⚙️ Funcionalidades Principais

* **Trading Autônomo Spot (Base)**: Executa trocas automatizadas (USDC ➔ ETH e vice-versa) na Uniswap V3 baseando-se em médias móveis de curto prazo (SMA-5) e exaustão de tendência.
* **Trading de Futuros Perpétuos (Hyperliquid)**: Abre posições LONG/SHORT com alavancagem isolada fixa (3x a 5x) na testnet/mainnet da Hyperliquid usando indicadores técnicos avançados (RSI).
* **Monitoramento Ativo de SL/TP**: Um loop assíncrono em segundo plano verifica os preços de marcação a cada 10 segundos e fecha posições a mercado caso as barreiras de risco (Stop Loss de 5% / Take Profit de 10%) sejam cruzadas.
* **Profit Sweep (Regra 10)**: O robô monitora os lucros acumulados (`undistributed_profit`). Sempre que ultrapassar **$200 USD**, o robô transfere automaticamente $200 para a carteira de custódia do usuário (`0x1d68FD5064AE7820E4597641FeCC94B9C47cF217`).
* **Paper Trading (Dry Run)**: Permite executar o agente em modo de simulação completa (com saldos de papel carregados localmente) utilizando os preços reais de mercado, ideal para validar a performance da estratégia sem risco de fundos.
* **Desempenho Multi-Temporal e Benchmarks**: O painel exibe comparativos da rentabilidade do agente em janelas de 24h a 90d contra estratégias clássicas como *Buy & Hold* e *DCA Diário*, buscando bater o mercado.

---

## 🛠️ Tecnologias e Dependências

* **Core**: Python 3.10+ & FastAPI / Uvicorn.
* **Agente Cognitivo**: LangChain & LangGraph (ReAct agent).
* **Modelos Disponíveis**: OpenAI GPT-4o-mini (padrão) ou Google Gemini (via `langchain-google-genai`).
* **Web3 Integration**: Coinbase AgentKit SDK & Hyperliquid Python SDK.
* **Frontend**: HTML5 semântico, Vanilla CSS e Vanilla Javascript para atualização assíncrona por Polling (3s).

---

## 🚀 Como Executar Localmente

### 1. Clonar o repositório
```bash
git clone https://github.com/pedrohedro/Base-AI-Agentic.git
cd Base-AI-Agentic
```

### 2. Ativar o Ambiente Virtual e Instalar Dependências
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configurar as Variáveis de Ambiente
Crie um arquivo `.env` na raiz do projeto baseado no exemplo abaixo:
```env
# Configurações do Cérebro LLM (Escolha 'openai' ou 'gemini')
LLM_PROVIDER="openai"

# Se utilizar OpenAI
OPENAI_API_KEY="sua_chave_openai_aqui"
OPENAI_MODEL="gpt-4o-mini"

# Se utilizar Gemini
GEMINI_API_KEY="sua_chave_gemini_aqui"
GEMINI_MODEL="gemini-2.5-flash"

# Configuração da Blockchain ('base-sepolia' ou 'base-mainnet')
NETWORK_ID="base-mainnet"
DRY_RUN="true"

# Porta e Endereço do Servidor
PORT=8000
HOST="0.0.0.0"
```

### 4. Executar o Servidor FastAPI
```bash
./venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 --loop asyncio
```

Acesse o painel no seu navegador através de: **`http://localhost:8000`**

---

## 💻 CLI de Controle (`agent_cli.py`)

Incluímos um utilitário CLI para interagir diretamente com o servidor de trading a partir do terminal. Isso permite que ferramentas externas (como o **Claude Code**) consultem e orquestrem o agente.

#### Comandos Disponíveis:
* **Ver status do sistema e saldos**: `./agent_cli.py status`
* **Ver posições abertas na Hyperliquid**: `./agent_cli.py futures`
* **Ver rentabilidade histórica**: `./agent_cli.py performance`
* **Exibir logs de análise em tempo real**: `./agent_cli.py logs --limit 15`
* **Ativar/Pausar trading autônomo**: `./agent_cli.py toggle`
* **Fechar manualmente uma posição perpétua**: `./agent_cli.py close ETH`
* **Enviar mensagens diretas de chat ao robô**: `./agent_cli.py chat "mensagem"`

---

## 📁 Estrutura de Arquivos

* `main.py`: Ponto de entrada do backend FastAPI, endpoints REST e loops de background de monitoramento SL/TP.
* `trading_agent.py`: Definição de carteira, inicialização do ReAct Agent, MockAgent de fallback cognitivo e ferramentas integradas (Hyperliquid SDK, indicadores técnicos).
* `agent_cli.py`: CLI em Python para controle via terminal/Claude Code.
* `trading_state.json`: Arquivo local de banco de dados onde são mantidos o histórico de swaps, PnL, posições simuladas e alvos de risco.
* `templates/index.html`: Interface visual premium do Dashboard.
* `static/css/style.css` e `static/js/app.js`: Folha de estilos e scripts assíncronos do painel.
