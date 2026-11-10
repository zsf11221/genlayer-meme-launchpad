# Live verification — Meme Launchpad

## Deployment

- Network: Stable Studionet (Chain ID 61999)
- RPC: https://studio.genlayer.com/api
- Contract: `0x26Ad5661901355C952a2109c53eAe6A5BdBE93D8`
- Contract page: https://explorer-studio.genlayer.com/address/0x26Ad5661901355C952a2109c53eAe6A5BdBE93D8
- Deploy transaction: `0x923cc17fa7296bfeacef7fe485c919de613caaefe19c7c832729052bbcb7b83f`
- Deploy source commit: `a3b0989d29ffd0e1902393986dcacff1b75864e9`
- Contract source SHA256: `3163d4e5d78e8c5ee484535b41d6f2035808e14e22c2be7c9acceb386ecd2514`
- Deployer (temporary script account): `0x1427A9eCFB9EC23ac7c7E4C6dda96d2aA9e9AA5F`

This is a redeployment for the steward follow-up (2026-11-10): the review
now fetches each listing's `evidence_source` URL itself, only the listing
creator may modify pending evidence, and post-decision witness entries are
capped at 5 per listing. The previous deployment is preserved in
`evidence/deployment-v1.json`.

## Transactions (every write waited for FINALIZED, then read back)

| # | Method | Transaction | Result |
|---:|--------|-------------|--------|
| 1 | `deploy` | `0x923cc17fa7296bfeacef7fe485c919de613caaefe19c7c832729052bbcb7b83f` | FINALIZED — contract deployed |
| 2 | `submit_listing` | `0x9148ecfb05dfe8d5303ba7f68a20d5eeb75c4fdef7cb3fdd0491fbd7baace802` | FINALIZED |
| 3 | `review_listing` | `0x7dff5f180de71c37a0a6a272024e52e5afa4eb86f96697a9b9a22317853a8548` | FINALIZED — LISTED (ORIGINAL_WORK) |
| 4 | `submit_listing` | `0x3805f16478ef5a0b94d5c2c1e0aebf99f0a1105f3ecebcf98a2894df7827b626` | FINALIZED |
| 5 | `review_listing` | `0x149793dc1863cd1bf5d4dea893cfdd1844675a6ebbadedc0ac3635829849f64f` | FINALIZED — GRADUATED (ORIGINAL_WORK) |
| 6 | `submit_listing` | `0x985df7892dd128763a165c9066a90bd7d8322a3162a296e0a35f3b532561f6c7` | FINALIZED |
| 7 | `review_listing` | `0x3850aecbc88a967f9d6f951751d17f58b6c230933b005cb10daed541d3e25ec9` | FINALIZED — REJECTED (THIN_EVIDENCE) |
| 8 | `claim_test_gen` | `0x902f0581f7c4b50f032067ac3c4b2406b1e0a165a24fca247c08bb46daf04be8` | FINALIZED |
| 9 | `buy` | `0xd9b6e66f6b3f18e8a907f6350ba0a14939c6408f16083695c00d990ae493aaad` | FINALIZED |
| 10 | `sell` | `0xc8fbba671ea45434b3d815abe10647572c2594193387606e482b0493c0a50abc` | FINALIZED |
| 11 | `buy` | `0x10873f2dc215181fd499e1feb8251b477c0dc2ad2486d560eb6d4adbd62a8c5b` | FINALIZED |
| 12 | `buy` | `0xa008a195d5687252f91c094a294a14803c8a68337deba1f7b6f6b18f9a0df2f1` | FINALIZED |
| 13 | `buy` | `0xbfe844b57553abdaa9ebd806c1cc80e92fed29c5a7238e6215b09ca0828ad9d6` | FINALIZED |
| 14 | `buy` | `0x620296d6baae50a1c074706b75ed20e328ea7fb46b0b1e9430bc2163134384f9` | FINALIZED |
| 15 | `buy` | `0xa4e067966dd502f5278e552bf211302b0b44bdc084370e48e53b60642b33b6b3` | FINALIZED |
| 16 | `buy` | `0x7a67cebc30eae7f8f3bfba1fc245db83d604cac07bc529a1faefe1cadbf81267` | FINALIZED |
| 17 | `buy` | `0x583dd19e3cab4fc5439192d28a1a4573ffec327f5c911034e868bc7e8efdfdda` | FINALIZED |
| 18 | `buy` | `0x9cbbd0f2e21b504f531e13ce6d048cd5ea199a9d700a624ef85d75eb2faecde0` | FINALIZED |
| 19 | `buy` | `0xb9687bdbae9726aca89013f836cc4f12c2643c207b2093232b43cee12f2bb2eb` | FINALIZED |
| 20 | `graduate` | `0x2e5dbd6eafbf89dbb21d4f06bc6c45245919da06acd00cae3139e517f524e62b` | FINALIZED — GRADUATED, fill 7481 bp |

## Read-back after the flow

- Listing 1 Pepe Garden (PGDN): LISTED, reason ORIGINAL_WORK, net bought 491995 microGEN, sold 12668103 tokens, fill 159 bp. Evidence source: https://raw.githubusercontent.com/zsf11221/genlayer-meme-launchpad/main/evidence/origins/pepe-garden.md
- Listing 2 Moon Cat (MCAT): GRADUATED, reason ORIGINAL_WORK, net bought 89100000 microGEN, sold 593326701 tokens, fill 7481 bp. Evidence source: https://raw.githubusercontent.com/zsf11221/genlayer-meme-launchpad/main/evidence/origins/moon-cat.md
- Listing 3 Moon Coin 100x (MOON): REJECTED, reason THIN_EVIDENCE, net bought 0 microGEN, sold 0 tokens, fill 0 bp. Evidence source: https://raw.githubusercontent.com/zsf11221/genlayer-meme-launchpad/main/README.md
- Price of listing 1: 39064 (microGEN per token, scaled by 1,000,000).
- Leaderboard order: 2 (GRADUATED, 7481 bp), 1 (LISTED, 159 bp), 3 (REJECTED, 0 bp).
- Deployer GEN ledger balance: 909498005 microGEN (1,000 GEN claimed, 91 GEN spent, 498,005 microGEN back from the sell).
- Deployer token balance on listing 1: 12668103 (25,336,206 bought, 12,668,103 sold).

## Earlier deployments (kept on record)

- Previous deployment (v1): contract `0x4778537493b94faFBa86Ac3ae57075DEdaF4154B`, deploy transaction `0x009044943f3d0e4a6f6dfe3a7de47a8d67709e39dd40b72b0b0ea8884ae900e9`. Full record: `evidence/deployment-v1.json`.
- First deployment: contract `0x125c72cE2bA3770F60c2b23636d04C73A3786962`, deploy transaction `0xcbc19b516e9039a3c716383e50b30542da8b27288bbb84e864bf5a562972154d`.
- Its first `review_listing` transaction `0xb440fc161bd8773bbf70c02288e958c03a1ab1e43ba4b69e9e211b8e7959eb59` reached FINALIZED, but validators disagreed after all rotations, so no state was written and the listing stayed PENDING_REVIEW. The consensus comparison was then changed (strict equality on the decision token instead of the full verdict string, and the review prompt was corrected for self-statement evidence), and the contract was redeployed. Full record: `evidence/review-attempt-1.json`.

## How to re-check

```python
from genlayer_py import create_client, create_account, studionet

client = create_client(chain=studionet, account=create_account())
addr = "0x26Ad5661901355C952a2109c53eAe6A5BdBE93D8"
client.read_contract(addr, "get_listing", args=["1"])
client.read_contract(addr, "get_leaderboard", args=[])
```

Or re-run the whole flow against a fresh deployment:

```
python3 scripts/deploy_studionet.py
```
