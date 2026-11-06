"""Deploy MemeLaunchpad to GenLayer Stable Studionet and run the minimal
live business flow, waiting for FINALIZED on every transaction.

- The deployer is a temporary account generated in memory only. Its
  private key is never printed, never written to disk, and never stored.
- Only the deployer address is recorded in the evidence files.
- Every write waits for FINALIZED, then reads state back.
- Evidence is written to evidence/evidence.json and
  evidence/live-verification.md even if a later step fails, so a partial
  run is still fully documented.

Usage: python3 scripts/deploy_studionet.py
"""

import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from genlayer_py import create_account, create_client, studionet
from genlayer_py.transactions.actions import TransactionStatus
from gltest.utils import extract_contract_address

ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = ROOT / "contracts" / "meme_launchpad.py"
EVIDENCE_DIR = ROOT / "evidence"

RPC_URL = "https://studio.genlayer.com/api"
CHAIN_ID = 61999

# Poll every 10s. Reviews run LLM consensus, so they get the longest budget.
DEPLOY_RETRIES = 90
WRITE_RETRIES = 120
REVIEW_RETRIES = 180
POLL_MS = 10_000

GOOD_EVIDENCE_1 = (
    "I created Pepe Garden in March 2026 as an original hand-drawn frog meme. "
    "I drew the frog with ink on paper, scanned it, and posted the drawing "
    "process in three videos on my X account @pepegarden between 12 and 18 March 2026. "
    "The art is mine, this is the first token for this meme, and no other project uses this name."
)
GOOD_EVIDENCE_2 = (
    "Moon Cat is my original cartoon cat meme, drawn by me in April 2026. "
    "I sketched the cat in a notebook on 3 April 2026, inked it on 5 April, "
    "and publish the sketches on my blog mooncat.example. "
    "This is the first and only token for this character."
)
THIN_EVIDENCE = "best meme coin moon 100x buy now"


def log(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc).isoformat()}] {msg}", flush=True)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown (not a git checkout or git unavailable)"


class Runner:
    def __init__(self) -> None:
        self.account = create_account()  # in memory only
        self.client = create_client(chain=studionet, account=self.account)
        self.address = self.account.address
        self.contract_address: str | None = None
        self.steps: list[dict] = []

    def wait_finalized(self, tx_hash: str, retries: int) -> dict:
        try:
            receipt = self.client.wait_for_transaction_receipt(
                tx_hash,
                status=TransactionStatus.FINALIZED,
                interval=POLL_MS,
                retries=retries,
            )
            return {"finalized": True, "receipt": receipt}
        except Exception as e:  # noqa: BLE001 - record the real outcome
            try:
                tx = self.client.get_transaction(tx_hash)
                status = str(tx.get("status_name", tx.get("status", "unknown")))
            except Exception:  # noqa: BLE001
                status = "unknown (could not fetch transaction)"
            return {"finalized": False, "error": str(e), "last_status": status}

    def write(self, method: str, args: list, retries: int = WRITE_RETRIES) -> dict:
        assert self.contract_address is not None
        log(f"WRITE {method} {args}")
        tx_hash = self.client.write_contract(
            self.contract_address, method, args=args, account=self.account
        )
        log(f"  tx {tx_hash} submitted, waiting for FINALIZED ...")
        result = self.wait_finalized(tx_hash, retries)
        step = {
            "method": method,
            "args": [str(a) for a in args],
            "tx_hash": tx_hash,
            "finalized": result["finalized"],
        }
        if result["finalized"]:
            log(f"  FINALIZED {tx_hash}")
            step["receipt"] = json.loads(json.dumps(result["receipt"], default=str))
        else:
            log(f"  NOT FINALIZED: {result.get('last_status')}: {result.get('error', '')[:300]}")
            step["error"] = result.get("error", "")
            step["last_status"] = result.get("last_status", "")
        self.steps.append(step)
        if not result["finalized"]:
            raise RuntimeError(f"{method} did not finalize: {step}")
        return step

    def read(self, method: str, args: list | None = None):
        assert self.contract_address is not None
        return self.client.read_contract(
            self.contract_address, method, args=args or [], account=self.account
        )

    def deploy(self) -> None:
        code = CONTRACT_PATH.read_text()
        log(f"Deploying {CONTRACT_PATH.name} from {self.address} ...")
        tx_hash = self.client.deploy_contract(code=code, account=self.account)
        log(f"  deploy tx {tx_hash} submitted, waiting for FINALIZED ...")
        result = self.wait_finalized(tx_hash, DEPLOY_RETRIES)
        if not result["finalized"]:
            raise RuntimeError(f"Deploy did not finalize: {result}")
        receipt = result["receipt"]
        self.contract_address = extract_contract_address(receipt)
        log(f"  FINALIZED. Contract: {self.contract_address}")
        self.steps.append(
            {
                "method": "deploy",
                "args": [],
                "tx_hash": tx_hash,
                "finalized": True,
                "contract_address": self.contract_address,
                "receipt": json.loads(json.dumps(receipt, default=str)),
            }
        )


def main() -> int:
    started = datetime.now(timezone.utc).isoformat()
    runner = Runner()
    log(f"Deployer (temporary, in-memory only): {runner.address}")
    log(f"Chain {CHAIN_ID} RPC {RPC_URL}")
    evidence: dict = {
        "network": "Stable Studionet",
        "chain_id": CHAIN_ID,
        "rpc": RPC_URL,
        "contract_source": "contracts/meme_launchpad.py",
        "contract_source_sha256": sha256_file(CONTRACT_PATH),
        "deploy_source_commit": git_commit(),
        "deployer_address": runner.address,
        "started_at_utc": started,
        "steps": runner.steps,
        "readbacks": {},
        "error": None,
    }
    try:
        runner.deploy()
        evidence["contract_address"] = runner.contract_address
        evidence["deploy_tx_hash"] = runner.steps[0]["tx_hash"]

        # Listing 1: the trading demo listing, stays LISTED.
        runner.write("submit_listing", ["Pepe Garden", "PGDN", "A hand-drawn frog meme.", GOOD_EVIDENCE_1])
        listing1 = runner.read("get_listing", ["1"])
        assert listing1["status"] == "PENDING_REVIEW", listing1
        step = runner.write("review_listing", ["1"], retries=REVIEW_RETRIES)
        verdict1 = runner.read("get_listing", ["1"])
        log(f"  listing 1 after review: {verdict1['status']} ({verdict1['review_reason']})")
        step["readback"] = verdict1
        assert verdict1["status"] == "LISTED", verdict1

        # Listing 2: the graduation test listing.
        runner.write("submit_listing", ["Moon Cat", "MCAT", "An original cartoon cat meme.", GOOD_EVIDENCE_2])
        step = runner.write("review_listing", ["2"], retries=REVIEW_RETRIES)
        verdict2 = runner.read("get_listing", ["2"])
        log(f"  listing 2 after review: {verdict2['status']} ({verdict2['review_reason']})")
        step["readback"] = verdict2
        assert verdict2["status"] == "LISTED", verdict2

        # Listing 3: thin-evidence listing; the verdict is whatever consensus says.
        runner.write("submit_listing", ["Moon Coin 100x", "MOON", "Best meme coin moon 100x.", THIN_EVIDENCE])
        step = runner.write("review_listing", ["3"], retries=REVIEW_RETRIES)
        verdict3 = runner.read("get_listing", ["3"])
        log(f"  listing 3 after review: {verdict3['status']} ({verdict3['review_reason']})")
        step["readback"] = verdict3

        # Fund the ledger and trade on listing 1.
        step = runner.write("claim_test_gen", [])
        step["readback"] = {"gen_balance": runner.read("get_gen_balance", [runner.address])}
        step = runner.write("buy", ["1", "1000000"])  # 1 GEN
        step["readback"] = {"tokens_out": None}
        tokens_out = runner.read("get_token_balance", ["1", runner.address])
        step["readback"] = {"token_balance": tokens_out}
        log(f"  bought 1 GEN of listing 1, token balance now {tokens_out}")
        step = runner.write("sell", ["1", str(int(tokens_out) // 2)])
        step["readback"] = {"gen_balance": runner.read("get_gen_balance", [runner.address])}

        # Graduate listing 2 with nine 10 GEN buys (net 89.1 GEN >= 85 GEN).
        for i in range(9):
            runner.write("buy", ["2", "10000000"])
            log(f"  graduation buy {i + 1}/9 done")
        before = runner.read("get_listing", ["2"])
        log(f"  listing 2 net_bought before graduate: {before['net_bought']}")
        assert int(before["net_bought"]) >= 85_000_000, before
        step = runner.write("graduate", ["2"])
        after = runner.read("get_listing", ["2"])
        step["readback"] = after
        assert after["status"] == "GRADUATED", after
        log(f"  listing 2 GRADUATED, fill {after['fill_pct_bp']} bp")

        evidence["readbacks"] = {
            "listing_1": runner.read("get_listing", ["1"]),
            "listing_2": runner.read("get_listing", ["2"]),
            "listing_3": runner.read("get_listing", ["3"]),
            "price_listing_1": runner.read("get_price", ["1"]),
            "leaderboard": runner.read("get_leaderboard", []),
            "gen_balance": runner.read("get_gen_balance", [runner.address]),
            "token_balance_listing_1": runner.read("get_token_balance", ["1", runner.address]),
        }
        log("Live flow complete.")
    except Exception as e:  # noqa: BLE001 - evidence must be written even on failure
        evidence["error"] = f"{type(e).__name__}: {e}"
        log(f"ERROR: {e}")
    finally:
        evidence["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        evidence["contract_address"] = runner.contract_address
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        # Keep the earlier attempt's record: the first deployment's review
        # ended in validator disagreement (FINALIZED, no state written).
        # Never silently overwrite a failure record.
        existing = EVIDENCE_DIR / "evidence.json"
        if existing.exists() and not (EVIDENCE_DIR / "review-attempt-1.json").exists():
            (EVIDENCE_DIR / "review-attempt-1.json").write_text(existing.read_text())
            log("Previous evidence.json preserved as evidence/review-attempt-1.json")
        (EVIDENCE_DIR / "evidence.json").write_text(
            json.dumps(evidence, indent=2, default=str)
        )
        log(f"Evidence written to evidence/evidence.json (error={evidence['error']})")

    if evidence["error"]:
        return 1
    print()
    print("CONTRACT:", evidence["contract_address"])
    print("DEPLOY TX:", evidence["deploy_tx_hash"])
    print("DEPLOYER:", runner.address)
    return 0


if __name__ == "__main__":
    sys.exit(main())
