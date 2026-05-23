import requests

address = "0xC5Afe3898aa4F7F5f60352dd02e2c86B2f1aafFC"

def fetch_eth_balance(address: str) -> float:
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_getBalance",
        "params": [address, "latest"],
        "id": 1
    }
    try:
        response = requests.post("https://sepolia.base.org", json={
            "jsonrpc": "2.0",
            "method": "eth_getBalance",
            "params": [address, "latest"],
            "id": 1
        }, timeout=10)
        if response.status_code == 200:
            result = response.json().get("result")
            if result:
                return int(result, 16) / 1e18
    except Exception as e:
        print(f"Error fetching ETH balance: {e}")
    return 0.0

def fetch_usdc_balance(address: str) -> float:
    usdc_address = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
    addr_clean = address.lower().replace("0x", "")
    data = "0x70a08231" + addr_clean.zfill(64)
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [{"to": usdc_address, "data": data}, "latest"],
        "id": 1
    }
    try:
        response = requests.post("https://sepolia.base.org", json=payload, timeout=10)
        if response.status_code == 200:
            result = response.json().get("result")
            if result and result != "0x":
                return int(result, 16) / 1_000_000.0
    except Exception as e:
        print(f"Error fetching USDC balance: {e}")
    return 0.0

eth = fetch_eth_balance(address)
usdc = fetch_usdc_balance(address)
print(f"Wallet: {address}")
print(f"ETH Balance: {eth} ETH")
print(f"USDC Balance: {usdc} USDC")
