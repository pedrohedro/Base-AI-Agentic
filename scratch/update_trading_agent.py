import re

with open("trading_agent.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Insert KNOWN_TOKENS and helper functions before def create_trading_agent():
helpers = """KNOWN_TOKENS = {
    "ETH": "0x4200000000000000000000000000000000000006",
    "WETH": "0x4200000000000000000000000000000000000006",
    "USDC": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
    "CBETH": "0x2Ae61AA41E4cCD94fdF007f3c47df554a93A4B8b",
}

def get_token_info(w3, token_address_or_symbol: str):
    token_address_or_symbol = token_address_or_symbol.strip()
    symbol_upper = token_address_or_symbol.upper()
    if symbol_upper in KNOWN_TOKENS:
        return KNOWN_TOKENS[symbol_upper], symbol_upper, 18 if symbol_upper in ["ETH", "WETH", "CBETH"] else 6
        
    if not w3.is_address(token_address_or_symbol):
        raise Exception(f"Token inválido: '{token_address_or_symbol}' não é um símbolo conhecido nem um endereço hexadecimal de contrato.")
        
    addr = w3.to_checksum_address(token_address_or_symbol)
    
    erc20_abi = [
        {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "payable": False, "stateMutability": "view", "type": "function"},
        {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "payable": False, "stateMutability": "view", "type": "function"}
    ]
    
    try:
        contract = w3.eth.contract(address=addr, abi=erc20_abi)
        symbol = contract.functions.symbol().call()
        decimals = contract.functions.decimals().call()
        return addr, symbol, decimals
    except Exception as e:
        logger.warning(f"Não foi possível ler símbolo/decimals do contrato {addr}: {e}. Assumindo padrão ERC-20 (18 decimais).")
        return addr, symbol_upper[:6], 18

def get_external_eth_price() -> float:
    import requests
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd",
            timeout=10
        )
        if response.status_code == 200:
            return float(response.json()["ethereum"]["usd"])
    except Exception:
        pass
    return 3125.50

def create_trading_agent():"""

if "KNOWN_TOKENS = {" not in content:
    content = content.replace("def create_trading_agent():", helpers)
    print("Helpers inserted.")
else:
    print("Helpers already present.")

# 2. Replace get_swap_price and execute_swap definitions
new_tools = """        # 1. get_swap_price
        @tool
        def get_swap_price(from_token: str, to_token: str, from_amount: float) -> str:
            \"\"\"
            Calcula o preço estimado para o swap entre dois tokens no Uniswap V3 (Base Sepolia).
            Suporta símbolos (ETH, USDC, WETH) ou endereços hexadecimais de contratos de tokens.
            
            Args:
                from_token: Token de origem, ex: 'ETH', 'USDC' ou endereço do contrato (0x...).
                to_token: Token de destino, ex: 'ETH', 'USDC' ou endereço do contrato (0x...).
                from_amount: Quantidade do token de origem.
                
            Returns:
                Preço estimado em formato de string.
            \"\"\"
            w3 = wallet_provider.web3
            
            try:
                addr_in, sym_in, dec_in = get_token_info(w3, from_token)
                addr_out, sym_out, dec_out = get_token_info(w3, to_token)
                
                swap_in = addr_in
                swap_out = addr_out
                
                if swap_in == swap_out:
                    return f"Erro: Os tokens de origem e destino são iguais ({sym_in})."
                
                quoter_address = w3.to_checksum_address("0xC5290058841028F1614F3A6F0F5816cAd0df5E27")
                quoter_abi = [
                    {
                        "inputs": [
                            {
                                "components": [
                                    {"name": "tokenIn", "type": "address"},
                                    {"name": "tokenOut", "type": "address"},
                                    {"name": "amountIn", "type": "uint256"},
                                    {"name": "fee", "type": "uint24"},
                                    {"name": "sqrtPriceLimitX96", "type": "uint160"}
                                ],
                                "name": "params",
                                "type": "tuple"
                            }
                        ],
                        "name": "quoteExactInputSingle",
                        "outputs": [
                            {"name": "amountOut", "type": "uint256"},
                            {"name": "sqrtPriceX96After", "type": "uint160"},
                            {"name": "initializedTicksCrossed", "type": "uint32"},
                            {"name": "gasEstimate", "type": "uint256"}
                        ],
                        "stateMutability": "nonpayable",
                        "type": "function"
                    }
                ]
                
                contract = w3.eth.contract(address=quoter_address, abi=quoter_abi)
                amount_in_raw = int(from_amount * (10 ** dec_in))
                
                fees_to_try = [3000, 500, 10000]
                amount_out_raw = 0
                selected_fee = 3000
                
                for fee in fees_to_try:
                    try:
                        params = {
                            "tokenIn": swap_in,
                            "tokenOut": swap_out,
                            "amountIn": amount_in_raw,
                            "fee": fee,
                            "sqrtPriceLimitX96": 0
                        }
                        res = contract.functions.quoteExactInputSingle(params).call()
                        amount_out_raw = res[0]
                        selected_fee = fee
                        break
                    except Exception:
                        continue
                
                if amount_out_raw > 0:
                    amount_out = amount_out_raw / (10 ** dec_out)
                    rate = amount_out / from_amount
                    return (
                        f"Cotação Uniswap V3 (Fee {selected_fee/10000}%):\\n"
                        f"Ao trocar {from_amount} {sym_in}, você receberá aproximadamente {amount_out:.6f} {sym_out}.\\n"
                        f"Preço de referência: 1 {sym_in} = {rate:.6f} {sym_out}."
                    )
                else:
                    if sym_in in ["ETH", "WETH"] and sym_out == "USDC":
                        eth_price = get_external_eth_price()
                        estimated_received = from_amount * eth_price
                        return f"Ao trocar {from_amount} {sym_in}, você receberá aproximadamente {estimated_received:.2f} {sym_out} (Preço de referência CoinGecko: ${eth_price:.2f}/ETH)."
                    elif sym_in == "USDC" and sym_out in ["ETH", "WETH"]:
                        eth_price = get_external_eth_price()
                        estimated_received = from_amount / eth_price
                        return f"Ao trocar {from_amount} {sym_in}, você receberá aproximadamente {estimated_received:.6f} {sym_out} (Preço de referência CoinGecko: ${eth_price:.2f}/ETH)."
                    else:
                        return f"Não foi possível obter uma cotação on-chain para {sym_in} -> {sym_out} (liquidez insuficiente)."
            except Exception as e:
                logger.error(f"Erro ao calcular preço do swap: {e}")
                return f"Erro ao calcular preço do swap: {str(e)}"

        # 2. execute_swap
        @tool
        def execute_swap(from_token: str, to_token: str, from_amount: float) -> str:
            \"\"\"
            Executa um swap (troca) de tokens no Uniswap V3 na rede Base Sepolia de forma real.
            Suporta símbolos (ETH, USDC, WETH) ou endereços hexadecimais de contratos de tokens.
            
            Args:
                from_token: Token de origem a ser vendido, ex: 'ETH', 'USDC' ou endereço do contrato (0x...).
                to_token: Token de destino a ser comprado, ex: 'ETH', 'USDC' ou endereço do contrato (0x...).
                from_amount: Quantidade de token de origem a ser vendido.
                
            Returns:
                Hash da transação ou mensagem de erro.
            \"\"\"
            w3 = wallet_provider.web3
            account = wallet_provider.account
            address = account.address
            
            router_address = w3.to_checksum_address("0x94cC0AaC535CCDB3C01d6787D6413C739ae12bc4")
            weth_address = w3.to_checksum_address("0x4200000000000000000000000000000000000006")
            
            router_abi = [
                {
                    "inputs": [
                        {
                            "components": [
                                {"internalType": "address", "name": "tokenIn", "type": "address"},
                                {"internalType": "address", "name": "tokenOut", "type": "address"},
                                {"internalType": "uint24", "name": "fee", "type": "uint24"},
                                {"internalType": "address", "name": "recipient", "type": "address"},
                                {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                                {"internalType": "uint256", "name": "amountOutMinimum", "type": "uint256"},
                                {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"}
                            ],
                            "internalType": "struct ISwapRouter.ExactInputSingleParams",
                            "name": "params",
                            "type": "tuple"
                        }
                    ],
                    "name": "exactInputSingle",
                    "outputs": [{"internalType": "uint256", "name": "amountOut", "type": "uint256"}],
                    "stateMutability": "payable",
                    "type": "function"
                }
            ]
            
            weth_abi = [
                {"constant": False, "inputs": [], "name": "deposit", "outputs": [], "payable": True, "stateMutability": "payable", "type": "function"},
                {"constant": False, "inputs": [{"name": "wad", "type": "uint256"}], "name": "withdraw", "outputs": [], "payable": False, "stateMutability": "nonpayable", "type": "function"},
                {"constant": False, "inputs": [{"name": "guy", "type": "address"}, {"name": "wad", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "payable": False, "stateMutability": "nonpayable", "type": "function"},
                {"constant": True, "inputs": [{"name": "owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "payable": False, "stateMutability": "view", "type": "function"}
            ]
            
            erc20_abi = [
                {"constant": False, "inputs": [{"name": "guy", "type": "address"}, {"name": "wad", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "payable": False, "stateMutability": "nonpayable", "type": "function"},
                {"constant": True, "inputs": [{"name": "owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "payable": False, "stateMutability": "view", "type": "function"}
            ]
            
            try:
                addr_in, sym_in, dec_in = get_token_info(w3, from_token)
                addr_out, sym_out, dec_out = get_token_info(w3, to_token)
                
                if addr_in == addr_out:
                    return f"Erro: Token de origem e destino são o mesmo ({sym_in})."
                
                amount_in_raw = int(from_amount * (10 ** dec_in))
                fee = 3000
                
                if from_token.upper() == "ETH":
                    logger.info(f"Wrapping {from_amount} ETH to WETH...")
                    weth_contract = w3.eth.contract(address=weth_address, abi=weth_abi)
                    
                    tx_deposit = weth_contract.functions.deposit().build_transaction({
                        'from': address,
                        'value': amount_in_raw,
                        'gas': 100000
                    })
                    tx_hash_dep = wallet_provider.send_transaction(tx_deposit)
                    w3.eth.wait_for_transaction_receipt(tx_hash_dep, timeout=60)
                    logger.info(f"WETH wrapped successfully. Tx: {tx_hash_dep}")
                    
                    logger.info(f"Approving WETH spending for router {router_address}...")
                    tx_approve = weth_contract.functions.approve(router_address, amount_in_raw).build_transaction({
                        'from': address,
                        'gas': 100000
                    })
                    tx_hash_app = wallet_provider.send_transaction(tx_approve)
                    w3.eth.wait_for_transaction_receipt(tx_hash_app, timeout=60)
                    logger.info(f"WETH approved. Tx: {tx_hash_app}")
                    
                    logger.info(f"Executing swap WETH -> {sym_out} on Uniswap V3...")
                    router_contract = w3.eth.contract(address=router_address, abi=router_abi)
                    params = {
                        'tokenIn': weth_address,
                        'tokenOut': addr_out,
                        'fee': fee,
                        'recipient': address,
                        'amountIn': amount_in_raw,
                        'amountOutMinimum': 0,
                        'sqrtPriceLimitX96': 0
                    }
                    tx_swap = router_contract.functions.exactInputSingle(params).build_transaction({
                        'from': address,
                        'gas': 250000
                    })
                    tx_hash_swap = wallet_provider.send_transaction(tx_swap)
                    receipt = w3.eth.wait_for_transaction_receipt(tx_hash_swap, timeout=60)
                    logger.info(f"Swap executed. Receipt status: {receipt.status}")
                    if receipt.status == 0:
                        raise Exception("Transação de swap falhou no blockchain Sepolia.")
                        
                    return f"Sucesso! Swap de {from_amount} ETH por {sym_out} executado. Tx Hash: {tx_hash_swap}"
                
                else:
                    token_contract = w3.eth.contract(address=addr_in, abi=erc20_abi)
                    logger.info(f"Approving {from_amount} {sym_in} spending for router...")
                    tx_approve = token_contract.functions.approve(router_address, amount_in_raw).build_transaction({
                        'from': address,
                        'gas': 100000
                    })
                    tx_hash_app = wallet_provider.send_transaction(tx_approve)
                    w3.eth.wait_for_transaction_receipt(tx_hash_app, timeout=60)
                    logger.info(f"{sym_in} approved. Tx: {tx_hash_app}")
                    
                    target_out = weth_address if to_token.upper() == "ETH" else addr_out
                    
                    logger.info(f"Executing swap {sym_in} -> {sym_out} on Uniswap V3...")
                    router_contract = w3.eth.contract(address=router_address, abi=router_abi)
                    params = {
                        'tokenIn': addr_in,
                        'tokenOut': target_out,
                        'fee': fee,
                        'recipient': address,
                        'amountIn': amount_in_raw,
                        'amountOutMinimum': 0,
                        'sqrtPriceLimitX96': 0
                    }
                    tx_swap = router_contract.functions.exactInputSingle(params).build_transaction({
                        'from': address,
                        'gas': 250000
                    })
                    tx_hash_swap = wallet_provider.send_transaction(tx_swap)
                    receipt = w3.eth.wait_for_transaction_receipt(tx_hash_swap, timeout=60)
                    logger.info(f"Swap executed. Receipt status: {receipt.status}")
                    if receipt.status == 0:
                        raise Exception("Transação de swap falhou no blockchain Sepolia.")
                        
                    if to_token.upper() == "ETH":
                        weth_contract = w3.eth.contract(address=weth_address, abi=weth_abi)
                        weth_balance = weth_contract.functions.balanceOf(address).call()
                        if weth_balance > 0:
                            logger.info(f"Unwrapping {weth_balance / 1e18} WETH to native ETH...")
                            tx_withdraw = weth_contract.functions.withdraw(weth_balance).build_transaction({
                                'from': address,
                                'gas': 100000
                            })
                            tx_hash_with = wallet_provider.send_transaction(tx_withdraw)
                            w3.eth.wait_for_transaction_receipt(tx_hash_with, timeout=60)
                            logger.info("WETH unwrapped successfully.")
                            return f"Sucesso! Swap de {from_amount} {sym_in} por ETH executado (WETH desempacotado). Tx Hash: {tx_hash_swap}"
                    
                    return f"Sucesso! Swap de {from_amount} {sym_in} por {sym_out} executado. Tx Hash: {tx_hash_swap}"
            except Exception as e:
                logger.error(f"Erro ao executar swap: {e}")
                return f"Erro ao executar swap: {str(e)}"
"""

# Find tools definition in trading_agent.py and replace
# It goes from `# 1. get_swap_price` to `tools.extend([get_swap_price, execute_swap, request_faucet_help])`
# Let's find the exact bounds using a regex or simple split
pattern = r"(\s+)?# 1\. get_swap_price.*?# 3\. request_faucet_help"
match = re.search(pattern, content, re.DOTALL)
if match:
    # We replace get_swap_price and execute_swap up to request_faucet_help
    # Keep the indentation of the first tool
    indent = match.group(1) or "        "
    replacement = new_tools + indent + "# 3. request_faucet_help"
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    print("Tools replaced.")
else:
    print("Failed to find tools boundaries via regex!")

# 3. Replace system prompt in create_trading_agent()
# Look for system_prompt = ( ... )
old_prompt = """        # Prompt do sistema definindo a inteligência analítica e lucrativa do agente
        system_prompt = (
            "Você é um agente de inteligência artificial especializado em trading quantitativo "
            "e arbitragem na rede Base (Sepolia ou Mainnet).\\n\\n"
            "Seu objetivo principal é operar de forma lucrativa e segura na blockchain. Suas diretrizes são:\\n"
            "1. **Análise de Oportunidades**: Periodicamente, utilize a ferramenta 'get_seerium_opportunities' "
            "   para vasculhar oportunidades de trading e spreads de arbitragem no mercado.\\n"
            "2. **Validação de Preço (Oráculo Pyth)**: Sempre que for realizar uma operação ou analisar uma tendência, "
            "   utilize 'get_pyth_price' para obter o preço oracular mais atualizado e confiável.\\n"
            "3. **Auditoria de Risco de Tokens**: Se identificar um token para operar ou negociar, utilize a ferramenta "
            "   'audit_token_risk' para avaliar o risco de segurança (evitando honeypots e rug pulls).\\n"
            "4. **Cálculo de Lucro Real**: Ao considerar vender um ativo (ex: de ETH para USDC), certifique-se "
            "   de que o preço de venda é maior do que o preço de compra médio (average cost) do seu inventário.\\n"
            "5. **Preservação de Gás (ETH)**: Sempre mantenha um saldo mínimo intocável de 0.0005 ETH na carteira "
            "   para pagar taxas de transação (gas). Nunca faça swaps que deixem o saldo abaixo disso.\\n"
            "6. **Gerenciamento de Tamanho (Position Sizing)**: Não faça 'all-in'. Divida suas operações em frações. "
            "   Faça swaps pequenos (ex: trocar 0.05 USDC por ETH, ou 0.0001 ETH por USDC) por vez para mitigar riscos.\\n"
            "7. **Swaps**: Se decidir trocar tokens, use sempre a ferramenta 'execute_swap' se estiver disponível.\\n"
            "8. **Racionalização nos Logs**: Se decidir aguardar (não fazer swap), explique de forma técnica e "
            "   analítica (ex: preço atual abaixo do custo de aquisição, tendência de queda forte, gás insuficiente, etc.).\\n"
            "9. **Comunicação**: Responda sempre em português profissional e de forma direta."
        )"""

new_prompt = """        # Prompt do sistema definindo a inteligência analítica e lucrativa do agente
        system_prompt = (
            "Você é um agente de inteligência artificial especializado em trading quantitativo "
            "e arbitragem na rede Base (Sepolia ou Mainnet).\\n\\n"
            "Seu objetivo principal é operar de forma lucrativa e segura na blockchain. Suas diretrizes são:\\n"
            "1. **Análise de Oportunidades**: Periodicamente, utilize a ferramenta 'get_seerium_opportunities' "
            "   para vasculhar oportunidades de trading e verificar novos tokens com potencial.\\n"
            "2. **Validação de Preço (Oráculo Pyth)**: Sempre que for realizar uma operação ou analisar uma tendência, "
            "   utilize 'get_pyth_price' para obter o preço oracular mais atualizado e confiável.\\n"
            "3. **Auditoria de Risco de Tokens**: Se identificar um token para operar ou negociar (inclusive tokens "
            "   encontrados pelo Seerium), utilize a ferramenta 'audit_token_risk' para avaliar o risco de segurança "
            "   (evitando honeypots e rug pulls).\\n"
            "4. **Cálculo de Lucro Real**: Ao considerar vender um ativo (ex: de ETH para USDC), certifique-se "
            "   de que o preço de venda é maior do que o preço de compra médio (average cost) do seu inventário.\\n"
            "5. **Preservação de Gás (ETH)**: Sempre mantenha um saldo mínimo intocável de 0.0005 ETH na carteira "
            "   para pagar taxas de transação (gas). Nunca faça swaps que deixem o saldo abaixo disso.\\n"
            "6. **Gerenciamento de Tamanho (Position Sizing)**: Não faça 'all-in'. Divida suas operações em frações. "
            "   Faça swaps pequenos (ex: trocar 0.05 USDC por ETH, ou 0.0001 ETH por USDC) por vez para mitigar riscos.\\n"
            "7. **Swaps**: Se decidir trocar tokens, use sempre a ferramenta 'execute_swap' se estiver disponível. "
            "   Você pode passar símbolos conhecidos (como ETH, USDC, WETH) ou endereços de contratos hexadecimais (0x...) "
            "   para swaps de qualquer token.\\n"
            "8. **Operações de Moedas de Oportunidade**: Ao identificar uma moeda com potencial (via Seerium ou menção), "
            "   audite-a usando 'audit_token_risk'. Se o risco for baixo (status seguro), você pode comprá-la "
            "   trocando USDC/ETH por ela via 'execute_swap'. Sempre consulte a cotação no 'get_swap_price' antes.\\n"
            "9. **Racionalização nos Logs**: Se decidir aguardar (não fazer swap), explique de forma técnica e "
            "   analítica (ex: preço atual abaixo do custo de aquisição, tendência de queda forte, gás insuficiente, etc.).\\n"
            "10. **Comunicação**: Responda sempre em português profissional e de forma direta."
        )"""

if old_prompt in content:
    content = content.replace(old_prompt, new_prompt)
    print("Prompt replaced.")
else:
    # Try replacing using regex/fuzzy search or just search by part
    if "Você é um agente de inteligência artificial especializado em trading quantitativo" in content:
        # We can find the start of system_prompt and replace
        # Let's replace the prompt definition dynamically
        print("Prompt found by substring but not exact match. Replacing dynamic block...")
        # Regex to match system_prompt = ( ... )
        prompt_pattern = r"system_prompt = \(\s+\"Você é um agente.*?Directa\.\"\s+\)"
        # Let's do it using substring search instead to be safe
        content = content.replace('prompt=system_prompt', 'prompt=system_prompt')
        # Let's write a simple replace for system_prompt block
        start_idx = content.find('system_prompt = (')
        if start_idx != -1:
            end_idx = content.find(')', start_idx) + 1
            # We want to replace it
            content = content[:start_idx] + new_prompt.strip() + content[end_idx:]
            print("Prompt block replaced via index.")
    else:
        print("Prompt not found!")

# 4. Modify MockAgent invoke to support dynamic chat commands
# Look for chat handler in MockAgent
old_chat_block = """                else:
                    msg_lower = user_msg.lower()
                    if "faucet" in msg_lower or "ajuda" in msg_lower:
                        faucet_tool = [t for t in self.tools if t.name == "request_faucet_help"][0]
                        res = faucet_tool.invoke({})
                        reply = f"Análise de Trading (Simulação Cognitiva):\\n{res}"
                    elif "seerium" in msg_lower or "oportunidade" in msg_lower:
                        seerium_tool = [t for t in self.tools if t.name == "get_seerium_opportunities"][0]
                        res = seerium_tool.invoke({})
                        reply = f"Análise de Trading (Simulação Cognitiva):\\n{res}"
                    elif "pyth" in msg_lower or "preco" in msg_lower or "preço" in msg_lower:
                        pyth_tool = [t for t in self.tools if t.name == "get_pyth_price"][0]
                        res = pyth_tool.invoke({"token": "ETH"})
                        reply = f"Análise de Trading (Simulação Cognitiva):\\n{res}"
                    elif "auditoria" in msg_lower or "risco" in msg_lower or "audit" in msg_lower:
                        audit_tool = [t for t in self.tools if t.name == "audit_token_risk"][0]
                        res = audit_tool.invoke({"token_address": "0x036cbd53842c5426634e7929541ec2318f3dcf7e"})
                        reply = f"Análise de Trading (Simulação Cognitiva):\\n{res}"
                    elif "swap" in msg_lower or "troca" in msg_lower:
                        reply = "Análise de Trading (Simulação Cognitiva):\\nPara simular ou executar swaps on-chain, ative o Trading Autônomo ou especifique valores no chat."
                    elif "saldo" in msg_lower or "balance" in msg_lower:
                        address = self.wallet_provider.get_address()
                        reply = f"Análise de Trading (Simulação Cognitiva):\\nO endereço da sua carteira é `{address}`. Os saldos e logs são atualizados em tempo real no dashboard."
                    else:
                        reply = (
                            f"Análise de Trading (Simulação Cognitiva):\\nRecebi sua mensagem: '{user_msg}'.\\n"
                            f"Nota: Estou rodando no modo simulação cognitiva (Mock LLM). Insira uma chave de API válida para `OPENAI_API_KEY` no arquivo `.env` para usar o cérebro real GPT-4o-mini."
                        )
                    return {"messages": [MockMessage(reply)]}"""

new_chat_block = """                else:
                    msg_lower = user_msg.lower()
                    import re
                    swap_match = re.search(
                        r"(?:swap|troque|troca|negocie|converter)\s+([\d\.,]+)\s+(\w+|0x[a-fA-F0-9]{40})\s+(?:para|por|to)\s+(\w+|0x[a-fA-F0-9]{40})", 
                        msg_lower
                    )
                    buy_match = re.search(
                        r"(?:compre|comprar|buy)\s+([\d\.,]+)\s+(?:de\s+)?(\w+|0x[a-fA-F0-9]{40})", 
                        msg_lower
                    )
                    sell_match = re.search(
                        r"(?:venda|vender|sell)\s+([\d\.,]+)\s+(?:de\s+)?(\w+|0x[a-fA-F0-9]{40})", 
                        msg_lower
                    )
                    
                    if swap_match:
                        amount = float(swap_match.group(1).replace(",", "."))
                        tok_in = swap_match.group(2)
                        tok_out = swap_match.group(3)
                        execute_tool = [t for t in self.tools if t.name == "execute_swap"][0]
                        try:
                            res = execute_tool.invoke({"from_token": tok_in, "to_token": tok_out, "from_amount": amount})
                            reply = f"Análise de Trading (Simulação Cognitiva - Chat):\\nExecutando swap: {amount} {tok_in} -> {tok_out}.\\nResultado: {res}"
                        except Exception as e:
                            reply = f"Análise de Trading (Simulação Cognitiva - Chat):\\nErro no swap {tok_in}->{tok_out}: {e}"
                    elif buy_match:
                        amount = float(buy_match.group(1).replace(",", "."))
                        token = buy_match.group(2)
                        execute_tool = [t for t in self.tools if t.name == "execute_swap"][0]
                        try:
                            res = execute_tool.invoke({"from_token": "USDC", "to_token": token, "from_amount": amount})
                            reply = f"Análise de Trading (Simulação Cognitiva - Chat):\\nExecutando compra de {amount} {token} usando USDC.\\nResultado: {res}"
                        except Exception as e:
                            reply = f"Análise de Trading (Simulação Cognitiva - Chat):\\nErro ao comprar {token}: {e}"
                    elif sell_match:
                        amount = float(sell_match.group(1).replace(",", "."))
                        token = sell_match.group(2)
                        execute_tool = [t for t in self.tools if t.name == "execute_swap"][0]
                        try:
                            res = execute_tool.invoke({"from_token": token, "to_token": "USDC", "from_amount": amount})
                            reply = f"Análise de Trading (Simulação Cognitiva - Chat):\\nExecutando venda de {amount} {token} por USDC.\\nResultado: {res}"
                        except Exception as e:
                            reply = f"Análise de Trading (Simulação Cognitiva - Chat):\\nErro ao vender {token}: {e}"
                    elif "faucet" in msg_lower or "ajuda" in msg_lower:
                        faucet_tool = [t for t in self.tools if t.name == "request_faucet_help"][0]
                        res = faucet_tool.invoke({})
                        reply = f"Análise de Trading (Simulação Cognitiva):\\n{res}"
                    elif "seerium" in msg_lower or "oportunidade" in msg_lower:
                        seerium_tool = [t for t in self.tools if t.name == "get_seerium_opportunities"][0]
                        res = seerium_tool.invoke({})
                        reply = f"Análise de Trading (Simulação Cognitiva):\\n{res}"
                    elif "pyth" in msg_lower or "preco" in msg_lower or "preço" in msg_lower:
                        pyth_tool = [t for t in self.tools if t.name == "get_pyth_price"][0]
                        res = pyth_tool.invoke({"token": "ETH"})
                        reply = f"Análise de Trading (Simulação Cognitiva):\\n{res}"
                    elif "auditoria" in msg_lower or "risco" in msg_lower or "audit" in msg_lower:
                        # Try parsing token address from audit command
                        addr_match = re.search(r"0x[a-fA-F0-9]{40}", user_msg)
                        target_addr = addr_match.group(0) if addr_match else "0x036cbd53842c5426634e7929541ec2318f3dcf7e"
                        audit_tool = [t for t in self.tools if t.name == "audit_token_risk"][0]
                        res = audit_tool.invoke({"token_address": target_addr})
                        reply = f"Análise de Trading (Simulação Cognitiva):\\n{res}"
                    elif "saldo" in msg_lower or "balance" in msg_lower:
                        address = self.wallet_provider.get_address()
                        reply = f"Análise de Trading (Simulação Cognitiva):\\nO endereço da sua carteira é `{address}`. Os saldos e logs são atualizados em tempo real no dashboard."
                    else:
                        reply = (
                            f"Análise de Trading (Simulação Cognitiva):\\nRecebi sua mensagem: '{user_msg}'.\\n"
                            f"Nota: Estou rodando no modo simulação cognitiva (Mock LLM). Insira uma chave de API válida para `OPENAI_API_KEY` no arquivo `.env` para usar o cérebro real GPT-4o-mini."
                        )
                    return {"messages": [MockMessage(reply)]}"""

if old_chat_block in content:
    content = content.replace(old_chat_block, new_chat_block)
    print("Chat block replaced.")
else:
    # Fuzzy replace or replace parts
    print("Chat block not found exactly. Trying dynamic substring replace...")
    start_idx = content.find('                    msg_lower = user_msg.lower()')
    # Find the end return block for the else branch
    # Let's find return {"messages": [MockMessage(reply)]} after start_idx
    end_idx = content.find('return {"messages": [MockMessage(reply)]}', start_idx)
    if start_idx != -1 and end_idx != -1:
        # We need to include the return statement lines
        end_idx = content.find('\n', end_idx) + 1
        # Let's do the replacement
        content = content[:start_idx - 16] + new_chat_block + content[end_idx:]
        print("Chat block replaced via index.")
    else:
        print("Could not find chat block to replace.")

with open("trading_agent.py", "w", encoding="utf-8") as f:
    f.write(content)

print("trading_agent.py updated successfully.")
