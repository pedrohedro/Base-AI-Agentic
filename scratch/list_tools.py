from coinbase_agentkit import (
    AgentKit,
    AgentKitConfig,
    EthAccountWalletProvider,
    EthAccountWalletProviderConfig,
    wallet_action_provider,
    erc20_action_provider,
    pyth_action_provider,
    cdp_api_action_provider,
    cdp_evm_wallet_action_provider
)
from coinbase_agentkit_langchain import get_langchain_tools
from eth_account import Account
import os

account = Account.create()
config = EthAccountWalletProviderConfig(
    account=account,
    chain_id="84532"
)
wallet_provider = EthAccountWalletProvider(config)

providers = [
    wallet_action_provider(),
    erc20_action_provider(),
    pyth_action_provider(),
]

# We don't have CDP keys configured, but let's see if cdp_api_action_provider can be initialized
try:
    providers.append(cdp_api_action_provider())
    print("cdp_api_action_provider initialized without CDP keys.")
except Exception as e:
    print(f"Failed to initialize cdp_api_action_provider: {e}")

try:
    providers.append(cdp_evm_wallet_action_provider())
    print("cdp_evm_wallet_action_provider initialized.")
except Exception as e:
    print(f"Failed to initialize cdp_evm_wallet_action_provider: {e}")

agent_kit = AgentKit(
    AgentKitConfig(
        wallet_provider=wallet_provider,
        action_providers=providers
    )
)

tools = get_langchain_tools(agent_kit)
print(f"Loaded {len(tools)} tools:")
for t in tools:
    print(f" - {t.name}: {t.description[:100]}...")
