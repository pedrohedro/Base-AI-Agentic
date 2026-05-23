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
    if "swap" in t.name:
        print(f"Tool name: {t.name}")
        print(f"Args: {t.args}")
