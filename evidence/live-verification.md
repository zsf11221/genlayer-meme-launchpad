# Live verification — Meme Launchpad

## Deployment

- Network: Stable Studionet (Chain ID 61999)
- RPC: https://studio.genlayer.com/api
- Contract: `0x4778537493b94faFBa86Ac3ae57075DEdaF4154B`
- Contract page: https://explorer-studio.genlayer.com/address/0x4778537493b94faFBa86Ac3ae57075DEdaF4154B
- Deploy transaction: `0x009044943f3d0e4a6f6dfe3a7de47a8d67709e39dd40b72b0b0ea8884ae900e9`
- Deploy source commit: `b91d61848186721ffbb49295f26cefb42dc4c9b1`
- Contract source SHA256: `83749b114262a1c23244e47226efaca631790db1d93573ab5356e59281faeec3`
- Deployer (temporary script account): `0xfe92B02f21CC742ba8305710B7059562baB268b8`

## Transactions (every write waited for FINALIZED, then read back)

| # | Method | Transaction | Result |
|---:|--------|-------------|--------|
| 1 | `deploy` | `0x009044943f3d0e4a6f6dfe3a7de47a8d67709e39dd40b72b0b0ea8884ae900e9` | FINALIZED — contract deployed |
| 2 | `submit_listing` | `0x551c53771c5202bfc68ad6f835aac02b0ff2c5295da1bc09ff4c1cb10e8ce775` | FINALIZED |
| 3 | `review_listing` | `0x314347f8dd3cfcc121e5f637153543760e3ef40ffb8f2179cfa1521a33594553` | FINALIZED — LISTED (CREDIBLE_CREATOR) |
| 4 | `submit_listing` | `0xa3ccc61edfb1261913d84939ec0707a9039f4923e0e7ee30934ba1716c271526` | FINALIZED |
| 5 | `review_listing` | `0x118d54a4add7ee75cf439c46c2b2de5c079cfb0eae9bc6733cf0a990e301fc1b` | FINALIZED — LISTED (ORIGINAL_WORK) |
| 6 | `submit_listing` | `0xa0c09057c45cc67f8be530e1cdbeeb4a33d65acc6eb82a663efda1fcda3898b1` | FINALIZED |
| 7 | `review_listing` | `0xce682007521e9145f57649a3543f2f53c5252ea3bb2e04ad6c7f18590456b4ad` | FINALIZED — REJECTED (THIN_EVIDENCE) |
| 8 | `claim_test_gen` | `0xee88650e3367b009067d731eff78c323efe228e947e40d9373b3e7afa69574ee` | FINALIZED |
| 9 | `buy` | `0x3086cad5a2791b3e5cf5191591b60f2f7527dd04169c853797f6e096bbff0b92` | FINALIZED |
| 10 | `sell` | `0x4f30ea6f493e89e2cd59144e7101c728f97f0f291c29ebaee39a43085ae2c5a5` | FINALIZED |
| 11 | `buy` | `0xc35d6a5aa3cc33eb8e465062099382d241bee328995256034a527fa6630b95bc` | FINALIZED |
| 12 | `buy` | `0xbebdc6fd7b3b5af221b3420148cd57fc5706034d6e8df5087bdb8ebbf4f52e62` | FINALIZED |
| 13 | `buy` | `0xcb9b98be8aa7c01c340ef8f1e4695d49d836c2152d11d79ea262fa149ceda258` | FINALIZED |
| 14 | `buy` | `0x9348e60fe8f49c2df50853b9e83f86aa214be302530961acb3c9404d9f6b5c00` | FINALIZED |
| 15 | `buy` | `0x1575049a660defd67da89efbdc30c93f94f26ed1986d611f7a70245128925bf0` | FINALIZED |
| 16 | `buy` | `0xc84a5d32564370cc904dce01743ffb31d48859737a1cf790d4a013854c87422c` | FINALIZED |
| 17 | `buy` | `0x115802cc59111a9eebc524787b5de258c50c73e8f7229e20168f57f5f6a51734` | FINALIZED |
| 18 | `buy` | `0xa5afbd5e739f76a42ad326924b4ade5dde16e75be408426e28200fc5a0df1c2d` | FINALIZED |
| 19 | `buy` | `0x6d2c9aba3d4c6cc209b645da3613818c64571c5c6a351f40123504a037e4ab76` | FINALIZED |
| 20 | `graduate` | `0xc56be456e56d966ca9557a354f902b8719aad91e7d18db367c8102b0eb47cc9e` | FINALIZED — GRADUATED, fill 7481 bp |

## Read-back after the flow

- Listing 1 Pepe Garden (PGDN): LISTED, reason CREDIBLE_CREATOR, net bought 491995 microGEN, sold 12668103 tokens, fill 159 bp.
- Listing 2 Moon Cat (MCAT): GRADUATED, reason ORIGINAL_WORK, net bought 89100000 microGEN, sold 593326701 tokens, fill 7481 bp.
- Listing 3 Moon Coin 100x (MOON): REJECTED, reason THIN_EVIDENCE, net bought 0 microGEN, sold 0 tokens, fill 0 bp.
- Price of listing 1: 39064 (microGEN per token, scaled by 1,000,000).
- Leaderboard order: 2 (GRADUATED, 7481 bp), 1 (LISTED, 159 bp), 3 (REJECTED, 0 bp).
- Deployer GEN ledger balance: 909498005 microGEN (1,000 GEN claimed, 91 GEN spent, 498,005 microGEN back from the sell).
- Deployer token balance on listing 1: 12668103 (25,336,206 bought, 12,668,103 sold).

## Earlier deployment (kept on record)

- First deployment: contract `0x125c72cE2bA3770F60c2b23636d04C73A3786962`, deploy transaction `0xcbc19b516e9039a3c716383e50b30542da8b27288bbb84e864bf5a562972154d`.
- Its first `review_listing` transaction `0xb440fc161bd8773bbf70c02288e958c03a1ab1e43ba4b69e9e211b8e7959eb59` reached FINALIZED, but validators disagreed after all rotations, so no state was written and the listing stayed PENDING_REVIEW. The consensus comparison was then changed (strict equality on the decision token instead of the full verdict string, and the review prompt was corrected for self-statement evidence), and the contract was redeployed above. Full record: `evidence/review-attempt-1.json`.

## How to re-check

```python
from genlayer_py import create_client, create_account, studionet

client = create_client(chain=studionet, account=create_account())
addr = "0x4778537493b94faFBa86Ac3ae57075DEdaF4154B"
client.read_contract(addr, "get_listing", args=["1"])
client.read_contract(addr, "get_leaderboard", args=[])
```

Or re-run the whole flow against a fresh deployment:

```
python3 scripts/deploy_studionet.py
```
