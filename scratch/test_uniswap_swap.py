from web3 import Web3
from eth_account import Account
import os

# Connect to Base Sepolia
w3 = Web3(Web3.HTTPProvider("https://sepolia.base.org"))

# Load private key from wallet_data.txt if it exists
wallet_file = "wallet_data.txt"
if os.path.exists(wallet_file):
    with open(wallet_file, "r") as f:
        priv_key = f.read().strip()
else:
    # Use dummy key for testing
    priv_key = Account.create().key.hex()

account = Account.from_key(priv_key)
print(f"Testing with account: {account.address}")

# Addresses
router_address = w3.to_checksum_address("0x94cC0AaC535CCDB3C01d6787D6413C739ae12bc4")
weth_address = w3.to_checksum_address("0x4200000000000000000000000000000000000006")
usdc_address = w3.to_checksum_address("0x036CbD53842c5426634e7929541eC2318f3dCF7e")

# ABIs
weth_abi = [
    {
        "constant": False,
        "inputs": [],
        "name": "deposit",
        "outputs": [],
        "payable": True,
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [{"name": "wad", "type": "uint256"}],
        "name": "withdraw",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [{"name": "guy", "type": "address"}, {"name": "wad", "type": "uint256"}],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [{"name": "owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    }
]

router_abi = [
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

# Create contracts
weth_contract = w3.eth.contract(address=weth_address, abi=weth_abi)
router_contract = w3.eth.contract(address=router_address, abi=router_abi)

# Check balances
eth_bal = w3.eth.get_balance(account.address)
weth_bal = weth_contract.functions.balanceOf(account.address).call()
print(f"ETH Balance: {eth_bal / 1e18} ETH")
print(f"WETH Balance: {weth_bal / 1e18} WETH")

# Test build deposit transaction
try:
    amount_to_wrap = int(0.0001 * 1e18)
    nonce = w3.eth.get_transaction_count(account.address)
    tx = weth_contract.functions.deposit().build_transaction({
        'from': account.address,
        'value': amount_to_wrap,
        'gas': 50000,
        'maxFeePerGas': w3.to_wei('1.5', 'gwei'),
        'maxPriorityFeePerGas': w3.to_wei('0.1', 'gwei'),
        'nonce': nonce,
        'chainId': 84532
    })
    print("Deposit tx built successfully:", tx)
except Exception as e:
    print("Deposit tx build failed:", e)

# Test build exactInputSingle transaction
try:
    params = {
        'tokenIn': weth_address,
        'tokenOut': usdc_address,
        'fee': 3000,
        'recipient': account.address,
        'amountIn': int(0.0001 * 1e18),
        'amountOutMinimum': 0,
        'sqrtPriceLimitX96': 0
    }
    tx_swap = router_contract.functions.exactInputSingle(params).build_transaction({
        'from': account.address,
        'gas': 250000,
        'maxFeePerGas': w3.to_wei('1.5', 'gwei'),
        'maxPriorityFeePerGas': w3.to_wei('0.1', 'gwei'),
        'nonce': nonce + 2, # dummy nonce
        'chainId': 84532
    })
    print("Swap tx built successfully:", tx_swap)
except Exception as e:
    print("Swap tx build failed:", e)
