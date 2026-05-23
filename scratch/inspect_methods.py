from coinbase_agentkit import (
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

print("send_transaction signature:")
print(inspect.signature(provider.send_transaction))

print("\nread_contract signature:")
print(inspect.signature(provider.read_contract))
