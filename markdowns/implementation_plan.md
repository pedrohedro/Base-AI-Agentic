# Implementation Plan - Profitable Agent Setup & Local Wallet Integration

This plan details the changes required to make the autonomous trading agent profitable, support standard Ethereum private keys as a fallback/alternative, load correct action providers (ERC20, Pyth, Wallet), and persist trading state.

## Proposed Changes

We will modify two key files:
1.  [trading_agent.py](file:///Users/pedrohedro/Base-AI-Agentic/trading_agent.py):
    *   Import `EthAccountWalletProvider`, `EthAccountWalletProviderConfig`, and `Account` from `eth_account`.
    *   Import action providers: `wallet_action_provider`, `erc20_action_provider`, and `pyth_action_provider` from `coinbase_agentkit`.
    *   Update `initialize_wallet_provider()` to:
        *   Generate a new standard Ethereum private key if no CDP credentials are found and no local private key is saved in `wallet_data.txt`.
        *   Save the private key securely in `wallet_data.txt`.
        *   Initialize the local wallet provider (`EthAccountWalletProvider`) when running in local account mode.
    *   Update `create_trading_agent()` to configure the loaded action providers in `AgentKitConfig`.
    *   Refine the system prompt to guide the agent to perform profitable, risk-managed trades.
2.  [main.py](file:///Users/pedrohedro/Base-AI-Agentic/main.py):
    *   Load and manage a local state file `trading_state.json` to persist the trade history, average buy price, total trades, and total profit/loss.
    *   Update `fetch_market_data()` to fetch the price, 24h change, and volume from CoinGecko.
    *   Update the autonomous trading loop to feed the current market data and trading state into the prompt.
    *   Inspect agent responses to automatically update the trading state when swaps are completed.

---

### [Component Name] Trading Core & Backend

#### [MODIFY] [trading_agent.py](file:///Users/pedrohedro/Base-AI-Agentic/trading_agent.py)
*   Add local Ethereum wallet support using `EthAccountWalletProvider` and `eth_account.Account`.
*   Import and register `wallet_action_provider()`, `erc20_action_provider()`, and `pyth_action_provider()` in `AgentKitConfig`.
*   Update the system prompt with clear guidelines on profit-taking, stop-loss, and gas fee preservation.

#### [MODIFY] [main.py](file:///Users/pedrohedro/Base-AI-Agentic/main.py)
*   Add state persistence in `trading_state.json`.
*   Improve market data fetching to query 24h change from CoinGecko.
*   Feed historical trade history and pricing metrics into the agent loop.
*   Parse successful swap execution events from agent results to update `trading_state.json`.

---

## Verification Plan

### Automated & Manual Verification
1.  **Dry-Run / Mock Initialization**:
    *   Run initialization scripts using virtual environment python to verify that imports and class instances work perfectly.
2.  **Wallet Generation & Funding**:
    *   Restart the server. A local Ethereum wallet will be generated (since CDP keys are not configured yet).
    *   Read `wallet_data.txt` to find the private key and corresponding public address.
    *   Verify the console logs print the generated address.
    *   Fund the address using a Base Sepolia Faucet.
3.  **End-to-End Simulation**:
    *   Once funded, monitor the terminal logs and web dashboard to ensure the agent reads the balance, fetches the CoinGecko pricing, and makes analytical trading decisions.
