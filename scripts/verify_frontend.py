"""Verify the deployed frontend flow end to end with a fresh script account.

This mirrors exactly what the website does (claim test GEN, then buy on
listing #1), using the same contract and the same wait-for-FINALIZED +
read-back discipline. The account is temporary and in memory only; its
private key is never printed, never written to disk, and never stored.
Only the account address and transaction hashes are reported.

Usage: python3 scripts/verify_frontend.py
"""

import json
import sys
from datetime import datetime, timezone

from genlayer_py import create_account, create_client, studionet
from genlayer_py.transactions.actions import TransactionStatus

CONTRACT = "0x4778537493b94faFBa86Ac3ae57075DEdaF4154B"
SITE = "https://zsf11221.github.io/genlayer-meme-launchpad/"
BUY_MICRO = "1000000"  # 1 GEN, the smallest meaningful demo trade


def log(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc).isoformat()}] {msg}", flush=True)


def main() -> int:
    account = create_account()
    client = create_client(chain=studionet, account=account)
    log(f"Temporary script account (in-memory only): {account.address}")
    log(f"Site under test: {SITE}")

    before = client.read_contract(CONTRACT, "get_listing", args=["1"], account=account)
    log(f"Listing #1 before: status={before['status']} sold={before['sold_tokens']} "
        f"net_bought={before['net_bought']} fill={before['fill_pct_bp']} bp")
    before_price = client.read_contract(CONTRACT, "get_price", args=["1"], account=account)
    log(f"Price #1 before: {before_price}")

    steps = []
    for method, args in [("claim_test_gen", []), ("buy", ["1", BUY_MICRO])]:
        tx_hash = client.write_contract(CONTRACT, method, args=args, account=account)
        log(f"WRITE {method} {args} -> {tx_hash}, waiting for FINALIZED ...")
        receipt = client.wait_for_transaction_receipt(
            tx_hash, status=TransactionStatus.FINALIZED, interval=10_000, retries=120
        )
        log(f"  FINALIZED {tx_hash}")
        steps.append({"method": method, "args": args, "tx_hash": tx_hash, "finalized": True})

    after = client.read_contract(CONTRACT, "get_listing", args=["1"], account=account)
    after_price = client.read_contract(CONTRACT, "get_price", args=["1"], account=account)
    gen_bal = client.read_contract(CONTRACT, "get_gen_balance", args=[account.address], account=account)
    tok_bal = client.read_contract(CONTRACT, "get_token_balance", args=["1", account.address], account=account)
    log(f"Listing #1 after: status={after['status']} sold={after['sold_tokens']} "
        f"net_bought={after['net_bought']} fill={after['fill_pct_bp']} bp")
    log(f"Price #1 after: {after_price}")
    log(f"Script account balances: GEN={gen_bal} microGEN, PGDN tokens={tok_bal}")

    tokens_bought = int(after["sold_tokens"]) - int(before["sold_tokens"])
    assert after["status"] == "LISTED", after
    assert tokens_bought > 0, "buy did not move sold_tokens"
    assert int(gen_bal) == 1_000_000_000 - int(BUY_MICRO), gen_bal
    assert int(tok_bal) == tokens_bought, (tok_bal, tokens_bought)

    result = {
        "site": SITE,
        "contract": CONTRACT,
        "script_account": account.address,
        "steps": steps,
        "readback": {
            "listing_1_before": {"sold_tokens": before["sold_tokens"], "net_bought": before["net_bought"],
                                "fill_pct_bp": before["fill_pct_bp"], "price": str(before_price)},
            "listing_1_after": {"sold_tokens": after["sold_tokens"], "net_bought": after["net_bought"],
                               "fill_pct_bp": after["fill_pct_bp"], "price": str(after_price)},
            "tokens_bought": tokens_bought,
            "gen_balance_micro": str(gen_bal),
            "token_balance": str(tok_bal),
        },
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
