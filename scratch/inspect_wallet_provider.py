from coinbase_agentkit import (
    AgentKit,
    AgentKitConfig,
    EthAccountWalletProvider,
    EthAccountWalletProviderConfig
)
from eth_account import Account
import inspect

account = Account.create()
config = EthAccountWalletProviderConfig(
    account=account,
    chain_id="84532"
)
provider = EthAccountWalletProvider(config)

print("EthAccountWalletProvider methods/attributes:")
for name, member in inspect.getmembers(provider):
    if not name.startswith("__"):
        print(f" - {name}")
