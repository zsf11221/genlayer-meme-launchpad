# Meme Launchpad

Website: https://zsf11221.github.io/genlayer-meme-launchpad/ (placeholder — the frontend is not deployed yet; this address will be confirmed once it is)

Meme token launcher on GenLayer Stable Studionet: bonding-curve trading with consensus-gated listing and graduation.

- Category: markets and wagers.
- Mechanism: consensus judges listing authenticity and sybil risk, which decides whether a meme may list and graduate; the bonding curve prices deterministically, and every buy/sell moves price, balances, fee split and graduation state.
- Interaction model: live curve trading board.
- Evolution state: price, fill %, holdings, leaderboard and graduation status evolve with every trade.

## Live deployment

- Network: Stable Studionet (Chain ID 61999), RPC https://studio.genlayer.com/api
- Contract: `0x4778537493b94faFBa86Ac3ae57075DEdaF4154B`
- Contract page: https://explorer-studio.genlayer.com/address/0x4778537493b94faFBa86Ac3ae57075DEdaF4154B
- Deploy transaction: `0x009044943f3d0e4a6f6dfe3a7de47a8d67709e39dd40b72b0b0ea8884ae900e9`
- Deploy source commit: `b91d61848186721ffbb49295f26cefb42dc4c9b1`
- Contract source SHA256: `83749b114262a1c23244e47226efaca631790db1d93573ab5356e59281faeec3`
- Full evidence: [`evidence/evidence.json`](evidence/evidence.json), [`evidence/live-verification.md`](evidence/live-verification.md)

## How it works

### Listing and consensus review

Anyone can submit a meme with `submit_listing(name, symbol, description, evidence)`. The listing starts as `PENDING_REVIEW`. `review_listing(listing_id)` asks GenLayer validators to judge the creator's evidence (origin, sources, creator history, in the creator's own words):

- The leader asks an LLM for exactly one line, `APPROVED|<CODE>` or `REJECTED|<CODE>`, with a fixed set of reason codes (`ORIGINAL_WORK`, `CREDIBLE_CREATOR`, `IMITATION`, `THIN_EVIDENCE`, `SYBIL_PATTERN`, `UNCLEAR_ORIGIN`).
- Each validator independently re-runs the same prompt on the same evidence. Consensus requires strict equality on the **decision** token (`APPROVED` vs `REJECTED`) — that token is what changes state. The reason code is leader-provided metadata and may differ between models.
- If consensus fails, nothing is written and the listing stays `PENDING_REVIEW`, retryable.
- A decided listing can never be re-reviewed. New evidence submitted afterwards is kept as a witness entry in `review_history`; the standing verdict is untouched.

### Bonding curve

Constant product `x * y = k`, all integer math, no floats anywhere.

- Units: GEN is accounted in microGEN (1 GEN = 1,000,000 microGEN). Tokens use smallest units with precision 0.
- Total supply is 1,000,000,000 tokens. 793,100,000 tokens sit on the curve against a virtual reserve of 30,000,000 microGEN (30 GEN). 206,900,000 tokens are held back as the graduation reserve and are never sold on the curve.
- Price is GEN reserve / token reserve, reported as microGEN per token scaled by 1,000,000.
- Every trade pays a 1% fee: 0.3% to the listing creator, 0.7% to the platform pool. Fees are ledger entries only.
- Graduation: cumulative net buys reach 85,000,000 microGEN (85 GEN). `graduate()` is an explicit trigger (there is no clock source): it checks the condition, records the fill % and locks the curve. Graduation is an internal ledger state change, not a migration to an external DEX.

### Test ledger

GEN balances are a nominal in-contract TEST ledger. `claim_test_gen()` credits 1,000 GEN once per address; buys and sells only move ledger entries. No real GEN is transferred by this contract. See [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md).

## Contract methods

| Method | Type | Description |
|---|---|---|
| `submit_listing(name, symbol, description, evidence)` | write | Create a listing, returns its id |
| `submit_evidence(listing_id, evidence)` | write | Replace evidence while pending; witness entry after a decision |
| `review_listing(listing_id)` | write | Consensus review, returns the verdict string |
| `claim_test_gen()` | write | Claim the one-time 1,000 GEN test credit |
| `buy(listing_id, amount_gen_micro)` | write | Buy tokens along the curve, returns tokens received |
| `sell(listing_id, token_amount)` | write | Sell tokens back, returns net GEN received |
| `graduate(listing_id)` | write | Graduate when net buys reach 85 GEN, returns fill % |
| `get_listing(id)` | view | Full listing state |
| `list_listings()` | view | All listings |
| `get_price(listing_id)` | view | Price in microGEN per token (scaled by 1,000,000) |
| `get_leaderboard()` | view | Listings ordered by fill % |
| `get_gen_balance(address)` | view | GEN ledger balance |
| `get_token_balance(listing_id, address)` | view | Token balance |

## Verify it yourself

```bash
# Pure-Python curve prototype (no GenLayer dependency)
python3 scripts/curve_prototype.py

# Contract tests in gltest direct mode (mocked LLM, real validator checks)
pip install -r requirements.txt
gltest tests/test_meme_launchpad.py -q

# Lint + semantic validation (GenVM v0.2.16)
GENVM_VERSION=v0.2.16 genvm-lint check contracts/meme_launchpad.py

# Full live redeploy + business flow on Studionet
python3 scripts/deploy_studionet.py
```

Test reports are in [`verification/`](verification/).

## Repository layout

- `contracts/meme_launchpad.py` — the intelligent contract
- `scripts/curve_prototype.py` — pure-Python mirror of the curve math with test vectors
- `scripts/deploy_studionet.py` — deploy + live business flow on Studionet
- `tests/test_meme_launchpad.py` — gltest direct-mode tests
- `evidence/` — deployment record, per-transaction FINALIZED receipts and read-backs
- `verification/` — prototype, lint and direct-test results
