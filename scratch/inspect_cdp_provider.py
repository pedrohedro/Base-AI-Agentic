from coinbase_agentkit import (
    CdpEvmWalletProvider,
    CdpEvmWalletProviderConfig
)
import inspect

print("CdpEvmWalletProvider methods:")
for name, member in inspect.getmembers(CdpEvmWalletProvider):
    if not name.startswith("__"):
        print(f" - {name}")
