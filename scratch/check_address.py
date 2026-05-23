from eth_account import Account
with open("wallet_data.txt", "r") as f:
    key = f.read().strip()
acc = Account.from_key(key)
print("Address:", acc.address)
