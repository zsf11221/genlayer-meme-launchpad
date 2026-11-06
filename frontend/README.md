# Meme Launchpad — frontend

Static Vite site for the Meme Launchpad contract on GenLayer Stable
Studionet (Chain ID 61999). The bonding curve itself is the trading
interface: drag along the curve to set a size, or type an amount.

- Contract: `0x4778537493b94faFBa86Ac3ae57075DEdaF4154B`
- Live site: https://zsf11221.github.io/genlayer-meme-launchpad/
- RPC: https://studio.genlayer.com/api
- Explorer: https://explorer-studio.genlayer.com

## Run

```sh
npm install
npm run dev
```

## Build and deploy (GitHub Pages)

```sh
npm run build
npm run check:i18n   # every UI string must exist in English and Chinese
```

The built `dist/` is published to the `gh-pages` branch; GitHub Pages
serves it at the live site above.

## How it talks to the chain

- Reads (`list_listings`, `get_price`, `get_leaderboard`,
  `get_gen_balance`, `get_token_balance`) use `genlayer-js` with no
  wallet — the board loads without connecting.
- Writes use `genlayer-js` `writeContract` and wait for
  `FINALIZED` via `waitForTransactionReceipt`, then read the contract
  state back before showing a result.
- Any injected EVM wallet (MetaMask, OKX, Rabby, Coinbase) can connect
  through `window.ethereum`. The site checks the wallet is on Chain ID
  61999 and asks it to switch if not.
- Without a wallet, the site offers a temporary in-browser test account
  (`createAccount()` from `genlayer-js`). Its key is generated in the
  browser, never leaves it, is never stored, and is discarded when the
  tab closes or the user presses “Discard test account”. Requests made
  with it are labelled as test-account requests in the interface.
- Amounts are string integers only — GEN amounts are converted from
  decimal input to microGEN with string math, never floats.
- Trade previews are calculated locally from the constant-product curve
  and are labelled as previews, not on-chain results.

## Known limits

- GEN balances are a nominal in-contract test ledger: `claim_test_gen`
  credits 1,000 GEN once per address. No real GEN moves.
- Prices come only from the constant-product curve; there is no
  external price feed.
- Graduation locks the curve; it does not migrate to an external
  exchange.
