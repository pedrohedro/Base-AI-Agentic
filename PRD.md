# Documento de Requisitos do Produto (PRD) - Base Agentic

## 1. Visão Geral do Produto
O **Base Agentic** é um robô de trading quantitativo totalmente autônomo com interface visual que opera de forma independente no ecossistema DeFi. O produto resolve a necessidade de investidores cripto de executarem estratégias de arbitragem spot e posições de futuros perpétuos com alavancagem de forma assistida ou autônoma 24/7, sem expor fundos a corretoras centralizadas e garantindo gerenciamento estrito de riscos.

---

## 2. Objetivos e Critérios de Sucesso
* **Operação Contínua (24/7)**: O loop autônomo deve analisar as condições de mercado constantemente sem travar ou vazar memória.
* **Mitigação de Risco Estrita**: Toda operação de futuros deve obrigatóriamente possuir parâmetros de Stop Loss e Take Profit calculados antes da abertura.
* **Dashboard em Tempo Real**: Uma interface responsiva que permita monitoramento, ativação, encerramento manual de posições e auditoria completa das decisões através de logs de fácil leitura.
* **Sweep de Dividendos**: Redistribuir lucros on-chain acumulados para a carteira de destino do usuário sempre que atingir a meta de $200 USD.

---

## 3. Especificações Funcionais

### 3.1. Cérebro Cognitivo e Decisor (LLM)
* **Modelos**: Suporte a OpenAI (`gpt-4o-mini`) e Google Gemini (`gemini-2.5-flash`).
* **Modo Simulado (Cognitive MockAgent)**: Caso nenhuma chave de API válida esteja presente, o sistema inicializa um mock cognitivo que executa as análises e comandos técnicos (swaps, abertura/fechamento de futuros) com base em indicadores matemáticos, eliminando barreiras de teste.
* **Prompt do Sistema**: Injeção da tese quantitativa e regras de negócio diretamente nas diretrizes da IA (limites de gás, alavancagem, regras de sweep).

### 3.2. Operações de Trading e Integrações
* **Spot (Base L2)**: Swaps automatizados via Uniswap V3 utilizando o SDK Coinbase AgentKit.
  * *Segurança*: Saldo mínimo de ETH mantido na carteira (0.0005 ETH) para evitar travamento de carteira por falta de gás.
* **Futuros Perpétuos (Hyperliquid L1)**:
  * Conexão nativa com a testnet da Hyperliquid usando chaves auto-custodiais.
  * Alavancagem fixa isolada de 3x a 5x.
  * Cálculo dinâmico do tamanho das ordens baseado no saldo livre de margem da conta.

### 3.3. Monitoramento de Risco (SL/TP Loop)
* Um thread em background em `main.py` roda a cada 10 segundos.
* Coleta os preços de marcação reais da Hyperliquid.
* Compara o preço atual com os alvos locais salvos no arquivo de estado.
* Dispara ordem de fechamento a mercado (`market_close`) caso:
  * Posição LONG atinja perda de 5% (SL) ou ganho de 10% (TP).
  * Posição SHORT atinja perda de 5% (SL) ou ganho de 10% (TP).

### 3.4. Relatório de Desempenho e Benchmarks
* Endpoint `/api/performance` calcula e compara a variação do patrimônio do agente contra:
  * **Buy & Hold**: Retorno percentual do ETH no período.
  * **DCA Diário**: Compra média diária de $1 USD em ETH no período.
* Exibição em abas temporais de `24H`, `48H`, `7D`, `14D`, `30D`, `60D` e `90D`.
* Badge dinâmico **"OUTPERFORM"** acionado se a rentabilidade percentual do agente bater ambas as estratégias passivas.

---

## 4. Requisitos Não Funcionais

### 4.1. Segurança
* **Armazenamento de Chaves**: A chave privada do agente (`wallet_data.txt`) e variáveis de ambiente sensíveis (`.env`) devem ficar restritas ao escopo da máquina local e estão configuradas para serem ignoradas no controle de versão do Git.
* **Isolamento de Erros**: Erros no RPC de blockchain ou na API de oráculos não devem interromper o loop periódico ou travar o servidor FastAPI.

### 4.2. Usabilidade e Interface (UX/UI)
* Estética Neon Premium Dark (Glassmorphism) com micro-animações.
* Polling assíncrono leve no frontend para atualização de dados sem recarga de página (3s para dados operacionais, 15s para performance).
* Botão de encerramento manual visível e com modal de confirmação para todas as posições ativas.

### 4.3. Interface para Desenvolvedores (Orquestração CLI)
* Script executável `agent_cli.py` expondo todas as ações do backend via terminal para ser facilmente consumível por ferramentas externas de IA Agentic (como o Claude Code).

---

## 5. Plano de Validação e Testes
1. **Validação Funcional (Dry Run)**: Validação local das rotas usando o simulador cognitivo com preços reais do oráculo Pyth.
2. **Validação On-chain**: Teste de conexão de swaps na Base Sepolia e abertura de ordens na Hyperliquid Testnet.
3. **Teste de Estresse de SL/TP**: Forçar um Stop Loss simulado via arquivo de estado e verificar se o loop assíncrono executa o fechamento em menos de 10 segundos.
