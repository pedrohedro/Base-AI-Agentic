from web3 import Web3

w3 = Web3(Web3.HTTPProvider("https://sepolia.base.org"))

factory_address = "0x4752ba5DBc23f44D87826276BF6Fd6b1C372aD24"
factory_abi = [
    {
        "inputs": [
            {"internalType": "address", "name": "tokenA", "type": "address"},
            {"internalType": "address", "name": "tokenB", "type": "address"},
            {"internalType": "uint24", "name": "fee", "type": "uint24"}
        ],
        "name": "getPool",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    }
]

weth = "0x4200000000000000000000000000000000000006"
usdc = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"

factory_contract = w3.eth.contract(address=w3.to_checksum_address(factory_address), abi=factory_abi)

for fee in [100, 500, 3000, 10000]:
    try:
        pool = factory_contract.functions.getPool(
            w3.to_checksum_address(weth),
            w3.to_checksum_address(usdc),
            fee
        ).call()
        print(f"Fee {fee}: Pool address = {pool}")
    except Exception as e:
        print(f"Fee {fee} failed: {e}")
