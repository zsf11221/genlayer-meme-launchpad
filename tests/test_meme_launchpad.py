"""Direct-mode tests for contracts/meme_launchpad.py (no simulator, no network).

LLM calls are mocked with direct_vm.mock_llm; the consensus validator is
exercised explicitly with direct_vm.run_validator().
"""

import pytest

CONTRACT = "contracts/meme_launchpad.py"

def _sender_hex(direct_vm):
    sender = direct_vm.sender
    return sender.as_hex if hasattr(sender, "as_hex") else "0x" + bytes(sender).hex()


GOOD_EVIDENCE = (
    "I created Pepe Garden in March 2026 as an original hand-drawn frog meme. "
    "I drew the frog with ink on paper, scanned it, and posted the drawing "
    "process in three videos on my X account @pepegarden between 12 and 18 March 2026. "
    "The art is mine, this is the first token for this meme, and no other project uses this name."
)

SYBIL_EVIDENCE = "best meme coin moon 100x buy now"


@pytest.fixture
def launchpad(direct_deploy):
    return direct_deploy(CONTRACT)


def _submit(contract, evidence=GOOD_EVIDENCE, name="Pepe Garden"):
    return contract.submit_listing(name, "PGDN", "A hand-drawn frog meme.", evidence)


def _approve_mock(direct_vm, verdict="APPROVED|ORIGINAL_WORK"):
    direct_vm.mock_llm("meme token listing applications", verdict)


def test_submit_creates_pending_listing(direct_vm, launchpad):
    listing_id = _submit(launchpad)
    assert listing_id == "1"
    listing = launchpad.get_listing("1")
    assert listing["status"] == "PENDING_REVIEW"
    assert listing["creator"].lower() == _sender_hex(direct_vm).lower()
    assert listing["gen_reserve"] == "30000000"
    assert listing["token_reserve"] == "793100000"
    assert listing["net_bought"] == "0"
    assert launchpad.get_price("1") == "37826"


def test_review_approves_with_mocked_llm(direct_vm, launchpad):
    _submit(launchpad)
    _approve_mock(direct_vm)
    verdict = launchpad.review_listing("1")
    assert verdict == "APPROVED|ORIGINAL_WORK"
    # The validator independently re-derives the same verdict: strict equality.
    assert direct_vm.run_validator() is True
    listing = launchpad.get_listing("1")
    assert listing["status"] == "LISTED"
    assert listing["review_reason"] == "ORIGINAL_WORK"
    assert "REVIEW|APPROVED|ORIGINAL_WORK" in listing["review_history"]


def test_review_rejects_and_cannot_be_overwritten(direct_vm, launchpad):
    _submit(launchpad, evidence=SYBIL_EVIDENCE)
    _approve_mock(direct_vm, "REJECTED|SYBIL_PATTERN")
    verdict = launchpad.review_listing("1")
    assert verdict == "REJECTED|SYBIL_PATTERN"
    assert direct_vm.run_validator() is True
    assert launchpad.get_listing("1")["status"] == "REJECTED"
    # Re-review is refused.
    with direct_vm.expect_revert("already reviewed"):
        launchpad.review_listing("1")
    # New evidence is kept as a witness; the standing verdict is untouched.
    launchpad.submit_evidence("1", "I swear this one is real, please relist.")
    listing = launchpad.get_listing("1")
    assert listing["status"] == "REJECTED"
    assert "CONTEST|I swear this one is real" in listing["review_history"]


def test_review_empty_evidence_fails_before_write(direct_vm, launchpad):
    _submit(launchpad, evidence="")
    with direct_vm.expect_revert("Evidence is empty"):
        launchpad.review_listing("1")
    assert launchpad.get_listing("1")["status"] == "PENDING_REVIEW"


def test_review_bad_llm_format_fails_before_write(direct_vm, launchpad):
    _submit(launchpad)
    _approve_mock(direct_vm, "Looks good to me, approve it!")
    with direct_vm.expect_revert():
        launchpad.review_listing("1")
    assert launchpad.get_listing("1")["status"] == "PENDING_REVIEW"


def test_validator_disagreement_is_detected(direct_vm, launchpad):
    _submit(launchpad)
    _approve_mock(direct_vm)
    verdict = launchpad.review_listing("1")
    assert verdict == "APPROVED|ORIGINAL_WORK"
    # Swap the mock so the validator sees a different verdict.
    direct_vm.clear_mocks()
    _approve_mock(direct_vm, "REJECTED|IMITATION")
    assert direct_vm.run_validator() is False


def test_validator_agrees_when_decision_matches_but_code_differs(direct_vm, launchpad):
    # Strict equality applies to the DECISION token; a different reason
    # code for the same decision must not veto consensus.
    _submit(launchpad)
    _approve_mock(direct_vm, "APPROVED|ORIGINAL_WORK")
    verdict = launchpad.review_listing("1")
    assert verdict == "APPROVED|ORIGINAL_WORK"
    direct_vm.clear_mocks()
    _approve_mock(direct_vm, "APPROVED|CREDIBLE_CREATOR")
    assert direct_vm.run_validator() is True
    direct_vm.clear_mocks()
    _approve_mock(direct_vm, "REJECTED|SYBIL_PATTERN")
    assert direct_vm.run_validator() is False


def _listed(direct_vm, launchpad):
    _submit(launchpad)
    _approve_mock(direct_vm)
    launchpad.review_listing("1")
    assert launchpad.get_listing("1")["status"] == "LISTED"


def test_claim_buy_sell_curve(direct_vm, launchpad):
    _listed(direct_vm, launchpad)
    assert launchpad.claim_test_gen() == "1000000000"
    with direct_vm.expect_revert("already claimed"):
        launchpad.claim_test_gen()

    p0 = int(launchpad.get_price("1"))
    assert p0 == 37826

    # Buy 1 GEN -> 25,336,206 tokens (matches the pure-Python prototype).
    out = launchpad.buy("1", "1000000")
    assert out == "25336206"
    p1 = int(launchpad.get_price("1"))
    assert p1 > p0, "buy must push the price up"
    assert launchpad.get_gen_balance(_sender_hex(direct_vm)) == "999000000"
    assert launchpad.get_token_balance("1", _sender_hex(direct_vm)) == "25336206"

    # Fee ledger: 1% of 1 GEN = 10,000 microGEN; creator 3,000 / platform 7,000.
    listing = launchpad.get_listing("1")
    assert listing["creator_fees"] == "3000"
    assert listing["platform_fees"] == "7000"
    assert listing["net_bought"] == "990000"

    # Sell half back: price falls, GEN comes back minus fee.
    back = launchpad.sell("1", "12668103")
    assert back == "498005"
    p2 = int(launchpad.get_price("1"))
    assert p2 < p1 and p2 > p0
    listing = launchpad.get_listing("1")
    assert listing["sold_tokens"] == "12668103"


def test_buy_requires_listed_and_balance(direct_vm, launchpad):
    _submit(launchpad)
    with direct_vm.expect_revert("not tradable"):
        launchpad.buy("1", "1000000")
    _listed(direct_vm, launchpad)
    with direct_vm.expect_revert("Insufficient GEN balance"):
        launchpad.buy("1", "1000000")


def test_graduation_flow(direct_vm, launchpad):
    _listed(direct_vm, launchpad)
    launchpad.claim_test_gen()

    # Too early: graduation must fail and leave the status untouched.
    launchpad.buy("1", "10000000")
    with direct_vm.expect_revert("Graduation needs"):
        launchpad.graduate("1")
    assert launchpad.get_listing("1")["status"] == "LISTED"

    # Accumulate net buys past 85 GEN with 10 GEN buys.
    for _ in range(8):
        launchpad.buy("1", "10000000")
    listing = launchpad.get_listing("1")
    assert int(listing["net_bought"]) >= 85_000_000
    fill = launchpad.graduate("1")
    assert int(fill) > 7000  # > 70% of the curve supply sold
    assert launchpad.get_listing("1")["status"] == "GRADUATED"
    # The curve is locked after graduation.
    with direct_vm.expect_revert("not tradable"):
        launchpad.buy("1", "1000000")
    with direct_vm.expect_revert("not tradable"):
        launchpad.sell("1", "1000")


def test_leaderboard_orders_by_fill(direct_vm, launchpad):
    _listed(direct_vm, launchpad)
    launchpad.claim_test_gen()
    launchpad.buy("1", "5000000")

    _submit(launchpad, name="Second Meme")
    _approve_mock(direct_vm, "APPROVED|CREDIBLE_CREATOR")
    launchpad.review_listing("2")

    board = launchpad.get_leaderboard()
    assert [row["id"] for row in board] == ["1", "2"]
    assert int(board[0]["fill_pct_bp"]) > int(board[1]["fill_pct_bp"])
    assert launchpad.list_listings()["2"]["name"] == "Second Meme"
