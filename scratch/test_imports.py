import coinbase_agentkit
print("Available attributes in coinbase_agentkit:")
for attr in dir(coinbase_agentkit):
    if not attr.startswith("_"):
        print(f" - {attr}")
