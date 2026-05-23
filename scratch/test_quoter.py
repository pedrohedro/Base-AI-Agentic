import os
from web3 import Web3

def test_quoter():
    w3 = Web3(Web3.HTTPProvider("https://sepolia.base.org"))
    quoter_v2_address = w3.to_checksum_address("0xC5290058841028F1614F3A6F0F5816cAd0df5E27") # QuoterV2 on Base Sepolia
    
    weth = w3.to_checksum_address("0x4200000000000000000000000000000000000006")
    usdc = w3.to_checksum_address("0x036CbD53842c5426634e7929541eC2318f3dCF7e")
    
    # QuoterV2 quoteExactInputSingle ABI
    quoter_abi = [
        {
            "inputs": [
                {
                    "components": [
                        {"name": "tokenIn", "type": "address"},
                        {"name": "tokenOut", "type": "address"},
                        {"name": "amountIn", "type": "uint256"},
                        {"name": "fee", "type": "uint24"},
                        {"name": "sqrtPriceLimitX96", "type": "uint160"}
                    ],
                    "name": "params",
                    "type": "tuple"
                }
            ],
            "name": "quoteExactInputSingle",
            "outputs": [
                {"name": "amountOut", "type": "uint256"},
                {"name": "sqrtPriceX96After", "type": "uint160"},
                {"name": "initializedTicksCrossed", "type": "uint32"},
                {"name": "gasEstimate", "type": "uint256"}
            ],
            "stateMutability": "nonpayable",
            "type": "function"
        }
    ]
    
    contract = w3.eth.contract(address=quoter_v2_address, abi=quoter_abi)
    try:
        amount_in = int(1e18) # 1 ETH
        params = {
            "tokenIn": weth,
            "tokenOut": usdc,
            "amountIn": amount_in,
            "fee": 3000,
            "sqrtPriceLimitX96": 0
        }
        res = contract.functions.quoteExactInputSingle(params).call()
        print(f"Quoter V2: 1 ETH = {res[0] / 1e6} USDC")
    except Exception as e:
        print(f"Quoter V2 failed: {e}")

if __name__ == '__main__':
    test_quoter()
