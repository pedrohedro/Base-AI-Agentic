from web3 import Web3

w3 = Web3(Web3.HTTPProvider("https://sepolia.base.org"))

pools = {
    100: "0x57183717A087d2fe3Ad890873877244c3B96156c",
    500: "0x94bfc0574FF48E92cE43d495376C477B1d0EEeC0",
    3000: "0x46880b404CD35c165EDdefF7421019F8dD25F4Ad",
    10000: "0x4664755562152EDDa3a3073850FB62835451926a"
}

weth = "0x4200000000000000000000000000000000000006"
usdc = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"

erc20_abi = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    }
]

weth_contract = w3.eth.contract(address=w3.to_checksum_address(weth), abi=erc20_abi)
usdc_contract = w3.eth.contract(address=w3.to_checksum_address(usdc), abi=erc20_abi)

for fee, pool_addr in pools.items():
    try:
        pool_checksum = w3.to_checksum_address(pool_addr)
        weth_bal = weth_contract.functions.balanceOf(pool_checksum).call() / 1e18
        usdc_bal = usdc_contract.functions.balanceOf(pool_checksum).call() / 1e6
        print(f"Pool Fee {fee} ({pool_addr}):")
        print(f"  WETH Balance: {weth_bal:.4f}")
        print(f"  USDC Balance: {usdc_bal:.4f}")
    except Exception as e:
        print(f"Failed to check pool {fee}: {e}")
