# Engenharia Reversa & Análise: `base.org/agents`

Este documento contém uma engenharia reversa completa da página oficial da Base para agentes autônomos ([base.org/agents](https://base.org/agents)), dividida na análise visual/tecnológica, no processo de criação de um agente de trading e nas estratégias de teste correspondentes.

---

## 1. 🔍 Engenharia Reversa e Componentes da Página

A página `base.org/agents` é construída como um portal de entrada e posicionamento da rede Base como a **infraestrutura financeira definitiva para Inteligência Artificial**. 

### Arquitetura Tecnológica (Front-end Stack)
*   **Framework**: Next.js (React) com renderização híbrida e hidratação dinâmica no cliente.
*   **Tema & Estilo**: Modo escuro forçado por padrão (`class="dark"` injetada via script inline no cabeçalho). Usa CSS modular moderno e utilitários de Tailwind CSS modificados.
*   **Tipografia Exclusiva**: Carrega fontes customizadas pré-carregadas por fontes woff2 para excelente performance e estilo:
    *   `Geist Mono`: Para elementos de código e terminal.
    *   `Google Sans Flex`: Para textos e interações fluidas.
    *   `Base Sans` e `Base Sans Rounded`: A identidade de marca geométrica e arredondada da Coinbase/Base.
    *   `Doto`: Uma fonte com estilo de matriz de pontos usada no cabeçalho animado.
*   **Efeitos Visuais**:
    *   **Background Dinâmico**: Elemento `<canvas>` acelerado por hardware na raíz do background para renderizar animações sutis de conexões neurais ou fluxo de blocos (com transição suave de opacidade).
    *   **Terminal Neon**: No lado direito da seção hero, há um painel imitando um terminal de comando com uma borda iluminada por gradiente cônico dinâmico e sombra de brilho neon (`box-shadow: 0 0 18px 2px rgba(34,75,255,0.25)`).
    *   **Caret Piscante**: O cabeçalho possui uma barra piscante (`animate-blink`) com a cor azul de destaque (`#224BFF`).
    *   **NumberFlow**: Uso da biblioteca `<NumberFlow>` (componente `number-flow-react`) para animar em tempo real os contadores das estatísticas da rede (ex: transações de agentes, volume de pagamento e quantidade de agentes ativos).

### Estrutura de Seções (Componentes Visuais)
1.  **Navbar Glassmorphic**: Header fixo no topo com desfoque de fundo (`backdrop-blur`) e links expansíveis para Soluções, Desenvolvedores, Ecossistema e Recursos.
2.  **Hero Section**: 
    *   Subtítulo em azul claro (`#5B8CFF`).
    *   Título de grande impacto: "Financial infrastructure for AI agents".
    *   Botões de Ação (CTAs): `Create Agent Wallet` (para configuração) e `Explore Services` (linkando para o marketplace [agentic.market](https://agentic.market)).
3.  **Use Cases Grid**: Apresenta cards em grid modular com contornos sutis de borda dividindo as principais frentes de uso de agentes:
    *   *Autonomous Trading*: Gestão de carteiras, trocas de tokens e rebalanceamento de portfólios no ecossistema DeFi.
    *   *Agentic Payments (x402 Protocol)*: Uso de stablecoins em microtransações pay-per-request para comprar APIs/serviços de IA (como inferência ou busca) de forma autônoma.
    *   *Monetize Your Services*: Venda de serviços e APIs criados por terceiros diretamente para outros agentes.
4.  **Network Metrics Panel**: Contadores numéricos dinâmicos mostrando a escala real da economia agentic na Base.
5.  **Ecosystem Showcase**: Lista de projetos em destaque construindo na Base:
    *   *Bankr*: Gerenciador autônomo de portfólio.
    *   *Cloudflare x402*: Middleware para aceitar pagamentos pay-per-request na borda (edge computing).
    *   *Virtuals*: Lançamento e coordenação de swarms (enxames) de agentes com economia de tokens própria.
6.  **Open Standards Advocacy**: Foco de comunicação em padrões abertos e interoperabilidade para evitar o lock-in de fornecedores (vendor lock-in):
    *   *x402*: Protocolo HTTP estendido para pagamentos nativos.
    *   *ERC-8004*: Padrão para identidade onchain de agentes de IA.

---

## 2. 🏗️ Como Criar um Agente de Trading na Base

Com base nas práticas e documentações de IA da Base, o fluxo de desenvolvimento de um agente de trading autônomo é estruturado da seguinte forma:

```
[CDP Developer Portal] ──> API Key & Wallet Secret 
                                │
[Agent Core Setup]    ──> Inicializa CdpEvmWalletProvider (Base Sepolia/Mainnet)
                                │
[AI Brain Setup]      ──> Inicializa LLM (ex: GPT-4o-mini) + AgentKit Tools
                                │
[DeFi Execution]      ──> LangGraph ReAct Loop (Swap, Transfer, Token Deploy)
```

### Passo 1: Obtenção de Credenciais e Setup do Wallet Provider
O agente necessita de chaves da **Coinbase Developer Platform (CDP)** para operar contas MPC descentralizadas diretamente.
*   **CDP_API_KEY_ID** e **CDP_API_KEY_SECRET**: Identificação do desenvolvedor.
*   **CDP_WALLET_SECRET**: Chave para geração de carteiras MPC determinísticas.

No código (Python), o provedor de carteira é inicializado carregando ou gerando o endereço localmente para persistência de dados:
```python
from coinbase_agentkit import CdpEvmWalletProvider, CdpEvmWalletProviderConfig

config = CdpEvmWalletProviderConfig(
    network_id="base-sepolia",  # Rede de testes padrão
    address=saved_wallet_address # Carrega endereço existente (ex: salvo em txt)
)
wallet_provider = CdpEvmWalletProvider(config)
```

### Passo 2: Integração com o AgentKit
O `AgentKit` converte as capacidades da carteira em ferramentas (tools) legíveis por modelos de linguagem (LLMs) através de integrações de orquestradores (como LangChain/LangGraph).
```python
from coinbase_agentkit import AgentKit, AgentKitConfig
from coinbase_agentkit_langchain import get_langchain_tools

# Inicializa o kit de ferramentas onchain
agent_kit = AgentKit(AgentKitConfig(wallet_provider=wallet_provider))

# Extrai as ferramentas no formato LangChain
tools = get_langchain_tools(agent_kit)
```

### Passo 3: Definição da Lógica Cognitiva e Regras de Risco
Utilizando o padrão ReAct (Reasoning and Acting), cria-se um agente inteligente onde a LLM decide autonomamente quando e como chamar as ferramentas:
```python
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

llm = ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_API_KEY)

system_prompt = (
    "Você é um agente autônomo de trading na rede Base.\n"
    "Diretriz de Risco: Nunca gaste todo o seu saldo em transações. "
    "Mantenha no mínimo 0.005 ETH para cobrir taxas de gás."
)

agent = create_react_agent(
    model=llm,
    tools=tools,
    state_modifier=system_prompt
)
```

---

## 3. 🧪 Como Testar o Agente de Trading de Forma Segura

Testar agentes financeiros de IA exige uma abordagem defensiva em várias camadas para evitar a perda de fundos reais e garantir que o modelo não execute transações indesejadas em loops infinitos.

### Camada 1: Testes em Ambiente de Sandbox (Sepolia Testnet)
*   **Configuração**: Nunca inicie os testes na Mainnet. Configure o `network_id` como `base-sepolia`.
*   **Torneira de Fundos (Faucet)**: Colete tokens de teste gratuitamente no faucet da Coinbase ou da Cloudflare e envie-os para o endereço gerado pelo agente (salvo em `wallet_data.txt`).

### Camada 2: Execuções Manuais via Chat de Comando
Antes de liberar o loop autônomo de background, valide a interpretação das ferramentas usando a API de chat direto com a LLM:
*   **Validação de Balanço**: Envie a mensagem `"Qual é o seu saldo atual e endereço de carteira?"`. O agente deve acionar a ferramenta de carteira, retornar os valores corretos e formatar a resposta no idioma esperado.
*   **Validação de Swap**: Teste uma operação de valor irrisório: `"Faça um swap de 0.0001 ETH para USDC"`. Acompanhe no terminal se ele chama a ferramenta correta e gera a transação de teste.

### Camada 3: Monitoramento do Loop Autônomo (Paper Trading & Dry-Run)
*   **Modo de Simulação (Dry-Run)**: Antes de conceder permissão de escrita de transação à LLM, configure um parâmetro no prompt forçando o agente a "simular" transações:
    > "Analise o mercado e responda nos logs qual transação você faria, mas não chame a ferramenta de swap on-chain."
*   **Temporizadores de Segurança**: Configure o intervalo de execução (`trading_interval_seconds`) com um tempo seguro (ex: 2 a 5 minutos) para que você tenha tempo de pausar o servidor caso o agente entre em um ciclo errático (loops de swaps gerados por feedbacks errados de LLM).
*   **Explorador de Blocos**: Use o [Base Sepolia Scan](https://sepolia.basescan.org) inserindo os hashes de transação gerados nos logs para inspecionar se as taxas de gás e o roteamento de liquidez (Uniswap v3) ocorreram conforme o esperado de forma bem-sucedida.
