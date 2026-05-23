from web3 import Web3
from eth_account import Account
import os
import time

w3 = Web3(Web3.HTTPProvider("https://sepolia.base.org"))

wallet_file = "wallet_data.txt"
if os.path.exists(wallet_file):
    with open(wallet_file, "r") as f:
        priv_key = f.read().strip()
else:
    print("wallet_data.txt not found!")
    exit(1)

account = Account.from_key(priv_key)
print(f"Address: {account.address}")
print(f"ETH Balance: {w3.eth.get_balance(account.address) / 1e18} ETH")

router_address = w3.to_checksum_address("0x94cC0AaC535CCDB3C01d6787D6413C739ae12bc4")
weth_address = w3.to_checksum_address("0x4200000000000000000000000000000000000006")
usdc_address = w3.to_checksum_address("0x036CbD53842c5426634e7929541eC2318f3dCF7e")

erc20_abi = [
    {"constant": False, "inputs": [{"name": "guy", "type": "address"}, {"name": "wad", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "payable": False, "stateMutability": "nonpayable", "type": "function"},
    {"constant": True, "inputs": [{"name": "owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "payable": False, "stateMutability": "view", "type": "function"},
    {"constant": True, "inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}], "name": "allowance", "outputs": [{"name": "remaining", "type": "uint256"}], "payable": False, "stateMutability": "view", "type": "function"}
]

# We will test two router ABIs: one with deadline in the struct, and one without.
router_abi_with_deadline = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "address", "name": "tokenIn", "type": "address"},
                    {"internalType": "address", "name": "tokenOut", "type": "address"},
                    {"internalType": "uint24", "name": "fee", "type": "uint24"},
                    {"internalType": "address", "name": "recipient", "type": "address"},
                    {"internalType": "uint256", "name": "deadline", "type": "uint256"},
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

router_abi_without_deadline = [
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

usdc = w3.eth.contract(address=usdc_address, abi=erc20_abi)
print(f"USDC Balance: {usdc.functions.balanceOf(account.address).call() / 1e6} USDC")
print(f"USDC Allowance for Router: {usdc.functions.allowance(account.address, router_address).call() / 1e6} USDC")

# Test 1: ABI with deadline
print("\n--- Testing ABI WITH deadline in struct ---")
try:
    router_with = w3.eth.contract(address=router_address, abi=router_abi_with_deadline)
    params = {
        'tokenIn': usdc_address,
        'tokenOut': weth_address,
        'fee': 3000,
        'recipient': account.address,
        'deadline': int(time.time()) + 600,
        'amountIn': int(0.05 * 1e6), # 0.05 USDC
        'amountOutMinimum': 0,
        'sqrtPriceLimitX96': 0
    }
    nonce = w3.eth.get_transaction_count(account.address)
    tx = router_with.functions.exactInputSingle(params).build_transaction({
        'from': account.address,
        'gas': 300000,
        'nonce': nonce,
        'chainId': 84532
    })
    print("Successfully built tx with deadline. Simulating transaction...")
    # Simulate
    output = w3.eth.call(tx)
    print("Simulation succeeded! Output:", output.hex())
    
    # Send transaction
    signed = w3.eth.account.sign_transaction(tx, priv_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"Sent swap tx: {tx_hash.hex()}")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    print(f"Receipt status: {receipt.status}")
except Exception as e:
    print(f"ABI WITH deadline failed: {e}")

# Test 2: ABI without deadline
print("\n--- Testing ABI WITHOUT deadline in struct ---")
try:
    router_without = w3.eth.contract(address=router_address, abi=router_abi_without_deadline)
    params = {
        'tokenIn': usdc_address,
        'tokenOut': weth_address,
        'fee': 3000,
        'recipient': account.address,
        'amountIn': int(0.05 * 1e6), # 0.05 USDC
        'amountOutMinimum': 0,
        'sqrtPriceLimitX96': 0
    }
    nonce = w3.eth.get_transaction_count(account.address)
    tx = router_without.functions.exactInputSingle(params).build_transaction({
        'from': account.address,
        'gas': 300000,
        'nonce': nonce,
        'chainId': 84532
    })
    print("Successfully built tx WITHOUT deadline. Simulating transaction...")
    # Simulate
    output = w3.eth.call(tx)
    print("Simulation succeeded! Output:", output.hex())
except Exception as e:
    print(f"ABI WITHOUT deadline failed: {e}")
