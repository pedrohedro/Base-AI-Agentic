"""
MCP Server - Base AI Agentic Trading Agent
Exposes the agent's REST API as tools for Claude Code and other MCP clients.
"""
import json
import httpx
from fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP(
    name="base-trading-agent"
)

BASE_URL = "http://localhost:8000"
TIMEOUT = 45.0  # Increased timeout for LLM reasoning propagation

async def _get(path: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}{path}", timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()

async def _post(path: str, payload: dict = {}) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BASE_URL}{path}", json=payload, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()

@mcp.tool()
async def status() -> str:
    """
    Retorna o status geral do agente spot na rede Base.
    Inclui endereço da carteira, saldos de ETH e USDC, custo médio de compra,
    número de trades e status do loop autônomo.
    """
    try:
        data = await _get("/api/status")
        return json.dumps(data, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Erro ao conectar ao agente: {e}. Certifique-se de que o backend FastAPI está rodando na porta 8000."

@mcp.tool()
async def futures_status() -> str:
    """
    Retorna o estado da conta de futuros perpétuos na Hyperliquid.
    Inclui margem disponível, valor da conta, posições abertas reais/simuladas
    e histórico de trades.
    """
    try:
        data = await _get("/api/futures/state")
        return json.dumps(data, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Erro ao conectar ao agente de futuros: {e}. Certifique-se de que o backend FastAPI está rodando na porta 8000."

@mcp.tool()
async def close_position(asset: str) -> str:
    """
    Encerra imediatamente uma posição de futuros perpétuos aberta na Hyperliquid.
    
    Args:
        asset: Símbolo do ativo para fechar a posição (ex: 'ETH', 'BTC', 'SOL').
    """
    try:
        payload = {"asset": asset.upper()}
        data = await _post("/api/futures/close_manual", payload)
        return json.dumps(data, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Erro ao fechar posição de {asset}: {e}"

@mcp.tool()
async def toggle_autonomous() -> str:
    """
    Ativa ou desativa o loop autônomo de trading do agente.
    """
    try:
        data = await _post("/api/toggle")
        return json.dumps(data, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Erro ao alterar status do loop autônomo: {e}"

@mcp.tool()
async def chat(message: str) -> str:
    """
    Envia uma mensagem ou comando em linguagem natural diretamente para o agente inteligente ReAct.
    Utilize para solicitar análises técnicas detalhadas, ordenar compras/vendas customizadas
    ou interagir de forma geral. A resposta é dada em português.
    
    Args:
        message: Instrução, comando ou pergunta para o agente.
    """
    try:
        payload = {"message": message}
        data = await _post("/api/chat", payload)
        return data.get("reply", json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as e:
        return f"Erro ao enviar mensagem para o agente: {e}"

if __name__ == "__main__":
    mcp.run()
