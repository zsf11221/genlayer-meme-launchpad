# Frontend verification — Meme Launchpad

## Website

- Live site: https://zsf11221.github.io/genlayer-meme-launchpad/
- Deployment: Vite static build (`frontend/`, `npm run build`) published to
  the `gh-pages` branch; GitHub Pages serves it at the address above.
  Pages build status: `built`, source `gh-pages` branch, path `/`.
- Site checks (2026-11-07 01:27 CST): homepage returns HTTP 200, page
  title “Meme Launchpad — GenLayer Studionet”, JS and CSS assets return
  HTTP 200, contract address present in the served page.
- Frontend source commit: see `git log` on `main` (frontend commit
  `3545907`).

## Contract

- Network: Stable Studionet (Chain ID 61999), RPC https://studio.genlayer.com/api
- Contract: `0x4778537493b94faFBa86Ac3ae57075DEdaF4154B`
- Contract page: https://explorer-studio.genlayer.com/address/0x4778537493b94faFBa86Ac3ae57075DEdaF4154B

## End-to-end trade (script account, same flow as the website)

A fresh temporary script account ran the same two calls the website
offers (claim test GEN, then buy on listing #1), waiting for FINALIZED
on each and reading the contract state back. Script:
`scripts/verify_frontend.py`. Verified 2026-11-06T17:29:42Z.

| Step | Method | Transaction | Result |
|---|---|---|---|
| 1 | `claim_test_gen` | `0xc648d923c8c73339dcee939d0143927a0a8070235364fcf3b17aee0029b936e2` | FINALIZED |
| 2 | `buy` (#1, 1 GEN = 1,000,000 microGEN) | `0xef0b5d91397a549de4683037fe3d88bd7eb8f0179a3d0f678f4ae645d8643671` | FINALIZED |

- Explorer links:
  - https://explorer-studio.genlayer.com/tx/0xc648d923c8c73339dcee939d0143927a0a8070235364fcf3b17aee0029b936e2
  - https://explorer-studio.genlayer.com/tx/0xef0b5d91397a549de4683037fe3d88bd7eb8f0179a3d0f678f4ae645d8643671
- Script account: `0xecb13D3034EEe734dB783B2f8314452Db08Daf07`
  (temporary, in-memory only; key never stored).

## Read-back after the trade

Listing #1 Pepe Garden (PGDN), before → after:

- Status: LISTED → LISTED
- Tokens sold: 12,668,103 → 37,213,910 (+24,545,807 bought for 1 GEN)
- Net bought: 491,995 → 1,481,995 microGEN
- Fill: 159 bp (1.59%) → 469 bp (4.69%)
- Price: 39,064 → 41,642 (microGEN per token, scaled by 1,000,000)

Script account after the trade:

- GEN ledger balance: 999,000,000 microGEN (1,000 claimed, 1 spent)
- PGDN token balance: 24,545,807 (equals the tokens bought)

## Chain state shown by the site (read via genlayer-js, same calls as the site)

- #1 Pepe Garden (PGDN): LISTED, fill 469 bp, price 41,642
- #2 Moon Cat (MCAT): GRADUATED, fill 7,481 bp, price 596,175
- #3 Moon Coin 100x (MOON): REJECTED (THIN_EVIDENCE), fill 0 bp, price 37,826
- Leaderboard order: 2, 1, 3.

## How to re-check

```sh
# Read the live state the site shows (no wallet needed)
python3 scripts/verify_frontend.py   # claim + 1 GEN buy, fresh account
```

Or open the site and press “Refresh from chain”; every transaction
from a session appears under Activity with its explorer link.
