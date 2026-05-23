from coinbase_agentkit import (
    AgentKit,
    AgentKitConfig,
    EthAccountWalletProvider,
    EthAccountWalletProviderConfig,
    cdp_evm_wallet_action_provider
)
from coinbase_agentkit_langchain import get_langchain_tools
from eth_account import Account

account = Account.create()
config = EthAccountWalletProviderConfig(
    account=account,
    chain_id="84532"
)
wallet_provider = EthAccountWalletProvider(config)
agent_kit = AgentKit(
    AgentKitConfig(
        wallet_provider=wallet_provider,
        action_providers=[cdp_evm_wallet_action_provider()]
    )
)

tools = get_langchain_tools(agent_kit)
for t in tools:
    if t.name == "CdpEvmWalletActionProvider_get_swap_price":
        print("Found get_swap_price langchain tool!")
        
        # Test 1: Zero Address
        try:
            res = t.invoke({
                "from_token": "0x0000000000000000000000000000000000000000",
                "to_token": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
                "from_amount": "0.0001"
            })
            print("Result with Zero Address:", res)
        except Exception as e:
            print("Failed with Zero Address:", e)
            
        # Test 2: WETH Address (0x4200000000000000000000000000000000000006)
        try:
            res = t.invoke({
                "from_token": "0x4200000000000000000000000000000000000006",
                "to_token": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
                "from_amount": "0.0001"
            })
            print("Result with WETH Address:", res)
        except Exception as e:
            print("Failed with WETH Address:", e)

        # Test 3: Eeeee... Address
        try:
            res = t.invoke({
                "from_token": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
                "to_token": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
                "from_amount": "0.0001"
            })
            print("Result with Eeeee... Address:", res)
        except Exception as e:
            print("Failed with Eeeee... Address:", e)
