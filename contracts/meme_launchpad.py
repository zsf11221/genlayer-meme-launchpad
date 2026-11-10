# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

"""Meme launchpad with a bonding curve on GenLayer Stable Studionet.

Category / mechanism / interaction / evolution (four lines):
- Category: markets and wagers.
- Mechanism: consensus judges listing authenticity and sybil risk, which
  decides whether a meme may list and graduate; the bonding curve prices
  deterministically, and every buy/sell moves price, balances, fee split
  and graduation state.
- Interaction model: live curve trading board.
- Evolution state: price, fill %, holdings, leaderboard and graduation
  status evolve with every trade.

Money design (all integers, no floats anywhere):
- GEN is accounted in microGEN: 1 GEN = 1_000_000 microGEN.
- Tokens use smallest units with precision 0: 1 token = 1 unit.
- Total supply is 1_000_000_000 tokens. 793_100_000 tokens sit on the
  constant-product curve (x * y = k) against a virtual reserve of
  30_000_000 microGEN (30 GEN). 206_900_000 tokens are held back as the
  graduation reserve and are never sold on the curve.
- Price is GEN reserve / token reserve, reported as microGEN per token
  scaled by 1_000_000 (integer).
- Every trade pays a 1% fee: 0.3% to the listing creator, 0.7% to the
  platform pool. Fees are ledger entries only, never transfers.
- Graduation: cumulative net buys reach 85_000_000 microGEN (85 GEN).
  graduate() is an explicit trigger (there is no clock source): it checks
  the condition, records the fill % at that moment and locks the curve.
  Graduation is an internal ledger state change, not a migration to an
  external DEX.
- GEN balances are a nominal in-contract TEST ledger. claim_test_gen()
  credits 1_000 GEN once per address; buys and sells only move ledger
  entries. No real GEN is transferred by this contract.

Consensus (review_listing):
- Evidence is authenticated, not just asserted. Every listing carries an
  evidence_source: a public https URL the creator supplies at submission.
  At review time the leader fetches that URL itself
  (gl.nondet.web.get) and judges the fetched content; each validator
  independently re-fetches the same URL and re-derives its verdict from
  what it fetched. If the source cannot be fetched (non-200, empty) the
  review fails before any write, so unauthenticated evidence can never
  produce a decision. The prompt judges originality, creator identity
  and sybil signals ONLY on the fetched source content together with the
  creator statement: approve only when the fetched source corroborates
  the creator and the first-token claim.
- The leader asks an LLM to judge the listing evidence and return exactly
  one line: "APPROVED|<CODE>" or "REJECTED|<CODE>", where <CODE> is one of
  a fixed set of reason codes. The validator independently re-runs the
  same prompt on the same evidence. The verdicts must agree under strict
  equality on the DECISION token (APPROVED vs REJECTED): that token is
  what changes state, so it is the thing consensus must settle exactly.
  The reason code is leader-provided metadata and may legitimately differ
  between models (for example THIN_EVIDENCE vs UNCLEAR_ORIGIN both mean
  REJECTED); a code difference alone must not veto an agreed decision.
  Requiring full-string equality on LLM-chosen reason codes made live
  consensus fail spuriously: on Studionet the first review ended in
  validator disagreement after all rotations even though the verdict
  itself was the contested point, not the wording.
- Any failure (empty evidence, unfetchable source, unparsable verdict,
  consensus disagreement) raises before any write, so the listing stays
  PENDING_REVIEW and can be retried.
- An already decided listing can never be re-reviewed. New evidence
  submitted afterwards is kept as a witness entry in review_history
  while the standing verdict stays untouched. Post-decision witness
  entries are bounded: at most MAX_WITNESSES entries per listing, and
  further witness submissions fail.
- Only the listing creator may modify pending evidence: submit_evidence
  while PENDING_REVIEW replaces the evidence (and, if given, the source
  URL) only when called by the creator; anyone else's call fails.
"""

from dataclasses import dataclass

from genlayer import *

# ---------------------------------------------------------------- units
MICRO_PER_GEN = 1_000_000

TOTAL_SUPPLY = 1_000_000_000
CURVE_SUPPLY = 793_100_000
GRADUATION_RESERVE = 206_900_000

GEN_RESERVE0 = 30_000_000  # 30 GEN, virtual GEN reserve (microGEN)
TOKEN_RESERVE0 = CURVE_SUPPLY  # virtual token reserve (smallest units)
K = GEN_RESERVE0 * TOKEN_RESERVE0  # constant product

FEE_NUM = 1  # 1% total fee
FEE_DEN = 100
CREATOR_FEE_SHARE_NUM = 30  # 30% of the fee goes to the creator
CREATOR_FEE_SHARE_DEN = 100  # the other 70% goes to the platform pool

GRADUATION_NET_BOUGHT = 85_000_000  # 85 GEN of net buys
CLAIM_AMOUNT = 1_000 * MICRO_PER_GEN  # 1000 GEN test credit, once per address

MAX_EVIDENCE_LEN = 2000
MAX_EVIDENCE_SOURCE_LEN = 500
MAX_WITNESSES = 5  # post-decision witness entries allowed per listing
FETCHED_EVIDENCE_MAX_CHARS = 4000

STATUS_PENDING = "PENDING_REVIEW"
STATUS_LISTED = "LISTED"
STATUS_REJECTED = "REJECTED"
STATUS_GRADUATED = "GRADUATED"

APPROVED_CODES = ("ORIGINAL_WORK", "CREDIBLE_CREATOR")
REJECTED_CODES = ("IMITATION", "THIN_EVIDENCE", "SYBIL_PATTERN", "UNCLEAR_ORIGIN")


@allow_storage
@dataclass
class Listing:
    id: str
    name: str
    symbol: str
    description: str
    evidence: str
    evidence_source: str
    witness_count: str
    creator: str
    status: str
    review_reason: str
    review_history: str
    gen_reserve: str
    token_reserve: str
    net_bought: str
    sold_tokens: str
    creator_fees: str
    platform_fees: str
    fill_pct_bp: str


def _parse_int(value: str, what: str) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        raise gl.vm.UserError("[EXPECTED] " + what + " must be a string integer, got: " + str(value))


def _fill_pct_bp(sold_tokens: int) -> int:
    return sold_tokens * 10_000 // CURVE_SUPPLY


def _split_fee(fee: int) -> tuple:
    creator_fee = fee * CREATOR_FEE_SHARE_NUM // CREATOR_FEE_SHARE_DEN
    platform_fee = fee - creator_fee
    return creator_fee, platform_fee


def _parse_verdict(raw: str) -> str:
    """Normalize raw LLM output to the strict verdict string.

    Only "APPROVED|<CODE>" / "REJECTED|<CODE>" with a code from the fixed
    sets is accepted. Anything else is an LLM error: raise before writing.
    Markdown fences and a leading "Verdict:" label are stripped first,
    because models sometimes add them despite being told not to.
    """
    if not isinstance(raw, str):
        raise gl.vm.UserError("[LLM_ERROR] Verdict is not a string")
    lines = []
    for line in raw.strip().split("\n"):
        stripped = line.strip()
        if stripped in ("```", "```json"):
            continue
        if stripped != "":
            lines.append(stripped)
    if len(lines) == 0:
        raise gl.vm.UserError("[LLM_ERROR] Verdict is empty")
    line = lines[0]
    if line.lower().startswith("verdict:"):
        line = line[len("verdict:"):].strip()
    parts = line.split("|")
    if len(parts) != 2:
        raise gl.vm.UserError("[LLM_ERROR] Verdict must be DECISION|CODE, got: " + line[:120])
    decision = parts[0].strip().upper()
    code = parts[1].strip().upper()
    if decision == "APPROVED" and code in APPROVED_CODES:
        return "APPROVED|" + code
    if decision == "REJECTED" and code in REJECTED_CODES:
        return "REJECTED|" + code
    raise gl.vm.UserError("[LLM_ERROR] Unknown verdict: " + line[:120])


def _verdict_decision(verdict: str) -> str:
    return verdict.split("|")[0]


def _validate_evidence_source(url: str) -> None:
    """An evidence source must be a public https URL (authenticated
    evidence: validators fetch it themselves at review time)."""
    if not isinstance(url, str) or url.strip() == "":
        raise gl.vm.UserError("[EXPECTED] evidence_source must not be empty")
    if len(url) > MAX_EVIDENCE_SOURCE_LEN:
        raise gl.vm.UserError("[EXPECTED] evidence_source exceeds 500 characters")
    if not url.startswith("https://"):
        raise gl.vm.UserError("[EXPECTED] evidence_source must be an https URL")


def _fetch_source_text(url: str) -> str:
    """Fetch the evidence source. Called inside nondet leader/validator
    functions, so every validator fetches the URL independently instead
    of trusting the submitted text. Any fetch failure raises before any
    write, so unauthenticated evidence can never produce a decision."""
    resp = gl.nondet.web.get(url)
    if resp.status != 200:
        raise gl.vm.UserError(
            "[EXPECTED] Evidence source could not be fetched: HTTP "
            + str(resp.status)
        )
    body = resp.body
    if body is None:
        raise gl.vm.UserError("[EXPECTED] Evidence source returned empty content")
    if isinstance(body, bytes):
        text = body.decode("utf-8", "ignore")
    else:
        text = str(body)
    if text.strip() == "":
        raise gl.vm.UserError("[EXPECTED] Evidence source returned empty content")
    return text[:FETCHED_EVIDENCE_MAX_CHARS]


def _review_prompt(name: str, symbol: str, description: str, evidence: str, evidence_source: str, fetched_text: str) -> str:
    return (
        "You review meme token listing applications for a launchpad. "
        "Judge ONLY the evidence below; do not use outside knowledge.\n"
        "Name: " + name + "\n"
        "Symbol: " + symbol + "\n"
        "Description: " + description + "\n"
        "Creator evidence (origin, sources, creator history, in the creator's own words):\n"
        + evidence + "\n"
        "Authenticated source evidence. The URL below was fetched by the "
        "reviewer itself from the creator-supplied source, it is NOT the "
        "creator's pasted claim:\n"
        "Source URL: " + evidence_source + "\n"
        "Fetched source content:\n" + fetched_text + "\n"
        "How to judge. Originality, creator identity and sybil signals are "
        "judged on the FETCHED source content together with the creator "
        "statement. The fetched source must corroborate the statement.\n"
        "1. APPROVE only when the fetched source corroborates the statement: "
        "it names the creator (or their public account), shows the creation "
        "process or dates, and supports that this is the first token for "
        "this meme, with no impersonation or sybil signal.\n"
        "2. REJECT if it imitates a well-known project, coin or brand (IMITATION).\n"
        "3. REJECT if the fetched source does not support the creator or "
        "origin claim at all, for example it is unrelated, empty of creator "
        "information, or contradicts the statement (UNCLEAR_ORIGIN). "
        "REJECT only if the statement itself is also empty, generic or "
        "hype-only with no creator information at all (THIN_EVIDENCE).\n"
        "4. REJECT if it reads like bulk sybil issuance: copy-paste text, no creator "
        "history, no origin story in either the statement or the fetched source (SYBIL_PATTERN).\n"
        "5. REJECT if origin is unclear and cannot be told apart from a copy "
        "(UNCLEAR_ORIGIN).\n"
        "When the fetched source corroborates a specific, detailed statement "
        "with no impersonation signal, choose APPROVED rather than REJECTED.\n"
        "Reply with EXACTLY ONE LINE and nothing else, no markdown, no extra words:\n"
        "APPROVED|ORIGINAL_WORK or APPROVED|CREDIBLE_CREATOR or "
        "REJECTED|IMITATION or REJECTED|THIN_EVIDENCE or REJECTED|SYBIL_PATTERN or REJECTED|UNCLEAR_ORIGIN"
    )


class MemeLaunchpad(gl.Contract):
    listings: TreeMap[str, Listing]
    next_listing_id: str
    gen_balances: TreeMap[Address, str]
    claimed: TreeMap[Address, str]
    token_balances: TreeMap[str, str]

    def __init__(self):
        self.next_listing_id = "1"

    # ------------------------------------------------------------ helpers
    def _get_listing(self, listing_id: str) -> Listing:
        if listing_id not in self.listings:
            raise gl.vm.UserError("[EXPECTED] Unknown listing: " + listing_id)
        return self.listings[listing_id]

    def _save_listing(self, listing: Listing) -> None:
        self.listings[listing.id] = listing

    def _token_key(self, listing_id: str, address_hex: str) -> str:
        return listing_id + ":" + address_hex

    def _gen_balance_of(self, address: Address) -> int:
        return _parse_int(self.gen_balances.get(address, "0"), "GEN balance")

    def _token_balance_of(self, listing_id: str, address_hex: str) -> int:
        key = self._token_key(listing_id, address_hex)
        return _parse_int(self.token_balances.get(key, "0"), "token balance")

    def _listing_dict(self, listing: Listing) -> dict:
        return {
            "id": listing.id,
            "name": listing.name,
            "symbol": listing.symbol,
            "description": listing.description,
            "evidence": listing.evidence,
            "evidence_source": listing.evidence_source,
            "witness_count": listing.witness_count,
            "creator": listing.creator,
            "status": listing.status,
            "review_reason": listing.review_reason,
            "review_history": listing.review_history,
            "gen_reserve": listing.gen_reserve,
            "token_reserve": listing.token_reserve,
            "net_bought": listing.net_bought,
            "sold_tokens": listing.sold_tokens,
            "creator_fees": listing.creator_fees,
            "platform_fees": listing.platform_fees,
            "fill_pct_bp": listing.fill_pct_bp,
        }

    # ------------------------------------------------------------ listing
    @gl.public.write
    def submit_listing(self, name: str, symbol: str, description: str, evidence: str, evidence_source: str) -> str:
        if name.strip() == "" or symbol.strip() == "":
            raise gl.vm.UserError("[EXPECTED] name and symbol must not be empty")
        if description.strip() == "":
            raise gl.vm.UserError("[EXPECTED] description must not be empty")
        if len(evidence) > MAX_EVIDENCE_LEN:
            raise gl.vm.UserError("[EXPECTED] evidence exceeds 2000 characters")
        _validate_evidence_source(evidence_source)
        listing_id = self.next_listing_id
        self.next_listing_id = str(int(listing_id) + 1)
        listing = Listing(
            id=listing_id,
            name=name,
            symbol=symbol,
            description=description,
            evidence=evidence,
            evidence_source=evidence_source,
            witness_count="0",
            creator=gl.message.sender_address.as_hex,
            status=STATUS_PENDING,
            review_reason="",
            review_history="SUBMITTED",
            gen_reserve=str(GEN_RESERVE0),
            token_reserve=str(TOKEN_RESERVE0),
            net_bought="0",
            sold_tokens="0",
            creator_fees="0",
            platform_fees="0",
            fill_pct_bp="0",
        )
        self.listings[listing_id] = listing
        return listing_id

    @gl.public.write
    def submit_evidence(self, listing_id: str, evidence: str, evidence_source: str = "") -> str:
        """Attach new evidence. While PENDING_REVIEW it replaces the evidence
        (and, if given, the source URL) under review, but only when called
        by the listing creator; anyone else's update fails. After a
        decision it is kept as a witness entry and the standing verdict is
        never changed; witness entries are bounded to MAX_WITNESSES per
        listing, further ones fail."""
        if len(evidence) > MAX_EVIDENCE_LEN:
            raise gl.vm.UserError("[EXPECTED] evidence exceeds 2000 characters")
        if evidence_source != "":
            _validate_evidence_source(evidence_source)
        listing = self._get_listing(listing_id)
        if listing.status == STATUS_PENDING:
            if gl.message.sender_address.as_hex.lower() != listing.creator.lower():
                raise gl.vm.UserError("[EXPECTED] Only the listing creator can modify pending evidence")
            listing.evidence = evidence
            if evidence_source != "":
                listing.evidence_source = evidence_source
            listing.review_history = listing.review_history + "\nEVIDENCE_UPDATE"
        else:
            witnesses = _parse_int(listing.witness_count, "witness_count")
            if witnesses >= MAX_WITNESSES:
                raise gl.vm.UserError("[EXPECTED] Post-decision witness limit reached")
            listing.witness_count = str(witnesses + 1)
            listing.review_history = (
                listing.review_history + "\nCONTEST|" + evidence
            )
        self._save_listing(listing)
        return listing.status

    @gl.public.write
    def review_listing(self, listing_id: str) -> str:
        listing = self._get_listing(listing_id)
        if listing.status != STATUS_PENDING:
            raise gl.vm.UserError("[EXPECTED] Listing already reviewed: " + listing.status)
        if listing.evidence.strip() == "":
            raise gl.vm.UserError("[EXPECTED] Evidence is empty, cannot review")

        def leader_fn():
            # The source URL is fetched here, inside the nondet call, so
            # every validator fetches it independently too (validator_fn
            # re-runs leader_fn). The verdict is judged on the fetched
            # content, not on the creator's pasted claim alone.
            fetched = _fetch_source_text(listing.evidence_source)
            prompt = _review_prompt(
                listing.name, listing.symbol, listing.description,
                listing.evidence, listing.evidence_source, fetched,
            )
            raw = gl.nondet.exec_prompt(prompt)
            return _parse_verdict(raw)

        def validator_fn(leaders_res):
            # Strict equality applies to the DECISION token: it is what
            # changes state. Reason codes may differ between models.
            # Never raise: under run_nondet_unsafe any validator error
            # counts as Disagree, so failures are explicit False votes.
            try:
                if not isinstance(leaders_res, gl.vm.Return):
                    # Leader errored: agree only if we fail the same way.
                    try:
                        leader_fn()
                    except gl.vm.UserError as e:
                        leader_msg = leaders_res.message if hasattr(leaders_res, "message") else ""
                        mine_msg = e.message if hasattr(e, "message") else str(e)
                        return mine_msg == leader_msg
                    except Exception:
                        return False
                    return False
                mine = leader_fn()
                return _verdict_decision(mine) == _verdict_decision(leaders_res.calldata)
            except Exception:
                return False

        verdict = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
        # Consensus reached. Only now, after agreement, write the outcome.
        decision, code = verdict.split("|")
        listing.review_reason = code
        listing.review_history = listing.review_history + "\nREVIEW|" + verdict
        if decision == "APPROVED":
            listing.status = STATUS_LISTED
        else:
            listing.status = STATUS_REJECTED
        self._save_listing(listing)
        return verdict

    # ------------------------------------------------------------ ledger
    @gl.public.write
    def claim_test_gen(self) -> str:
        sender = gl.message.sender_address
        if sender in self.claimed:
            raise gl.vm.UserError("[EXPECTED] Test GEN already claimed by this address")
        self.claimed[sender] = "1"
        new_balance = self._gen_balance_of(sender) + CLAIM_AMOUNT
        self.gen_balances[sender] = str(new_balance)
        return str(new_balance)

    # ------------------------------------------------------------ trading
    @gl.public.write
    def buy(self, listing_id: str, amount_gen_micro: str) -> str:
        listing = self._get_listing(listing_id)
        if listing.status != STATUS_LISTED:
            raise gl.vm.UserError("[EXPECTED] Listing is not tradable: " + listing.status)
        amount = _parse_int(amount_gen_micro, "amount_gen_micro")
        if amount <= 0:
            raise gl.vm.UserError("[EXPECTED] Buy amount must be positive")
        sender = gl.message.sender_address
        gen_balance = self._gen_balance_of(sender)
        if gen_balance < amount:
            raise gl.vm.UserError("[EXPECTED] Insufficient GEN balance")
        fee = amount * FEE_NUM // FEE_DEN
        net = amount - fee
        gen_reserve = _parse_int(listing.gen_reserve, "gen_reserve")
        token_reserve = _parse_int(listing.token_reserve, "token_reserve")
        new_gen = gen_reserve + net
        new_token = K // new_gen
        tokens_out = token_reserve - new_token
        if tokens_out <= 0:
            raise gl.vm.UserError("[EXPECTED] Buy too small to move the curve")
        creator_fee, platform_fee = _split_fee(fee)
        self.gen_balances[sender] = str(gen_balance - amount)
        key = self._token_key(listing_id, sender.as_hex)
        self.token_balances[key] = str(self._token_balance_of(listing_id, sender.as_hex) + tokens_out)
        listing.gen_reserve = str(new_gen)
        listing.token_reserve = str(new_token)
        listing.net_bought = str(_parse_int(listing.net_bought, "net_bought") + net)
        listing.sold_tokens = str(_parse_int(listing.sold_tokens, "sold_tokens") + tokens_out)
        listing.creator_fees = str(_parse_int(listing.creator_fees, "creator_fees") + creator_fee)
        listing.platform_fees = str(_parse_int(listing.platform_fees, "platform_fees") + platform_fee)
        listing.fill_pct_bp = str(_fill_pct_bp(_parse_int(listing.sold_tokens, "sold_tokens")))
        self._save_listing(listing)
        return str(tokens_out)

    @gl.public.write
    def sell(self, listing_id: str, token_amount: str) -> str:
        listing = self._get_listing(listing_id)
        if listing.status != STATUS_LISTED:
            raise gl.vm.UserError("[EXPECTED] Listing is not tradable: " + listing.status)
        amount = _parse_int(token_amount, "token_amount")
        if amount <= 0:
            raise gl.vm.UserError("[EXPECTED] Sell amount must be positive")
        sender = gl.message.sender_address
        token_balance = self._token_balance_of(listing_id, sender.as_hex)
        if token_balance < amount:
            raise gl.vm.UserError("[EXPECTED] Insufficient token balance")
        gen_reserve = _parse_int(listing.gen_reserve, "gen_reserve")
        token_reserve = _parse_int(listing.token_reserve, "token_reserve")
        new_token = token_reserve + amount
        new_gen = K // new_token
        gross = gen_reserve - new_gen
        if gross <= 0:
            raise gl.vm.UserError("[EXPECTED] Sell too small to move the curve")
        fee = gross * FEE_NUM // FEE_DEN
        net_gen = gross - fee
        creator_fee, platform_fee = _split_fee(fee)
        key = self._token_key(listing_id, sender.as_hex)
        self.token_balances[key] = str(token_balance - amount)
        self.gen_balances[sender] = str(self._gen_balance_of(sender) + net_gen)
        listing.gen_reserve = str(new_gen)
        listing.token_reserve = str(new_token)
        listing.net_bought = str(_parse_int(listing.net_bought, "net_bought") - net_gen)
        listing.sold_tokens = str(_parse_int(listing.sold_tokens, "sold_tokens") - amount)
        listing.creator_fees = str(_parse_int(listing.creator_fees, "creator_fees") + creator_fee)
        listing.platform_fees = str(_parse_int(listing.platform_fees, "platform_fees") + platform_fee)
        listing.fill_pct_bp = str(_fill_pct_bp(_parse_int(listing.sold_tokens, "sold_tokens")))
        self._save_listing(listing)
        return str(net_gen)

    @gl.public.write
    def graduate(self, listing_id: str) -> str:
        """Explicit graduation trigger (no clock source on GenVM).

        Succeeds only when cumulative net buys reach 85 GEN. Records the
        fill % at graduation and locks the curve: later buy/sell calls
        fail because the status is no longer LISTED.
        """
        listing = self._get_listing(listing_id)
        if listing.status != STATUS_LISTED:
            raise gl.vm.UserError("[EXPECTED] Only a LISTED listing can graduate: " + listing.status)
        net_bought = _parse_int(listing.net_bought, "net_bought")
        if net_bought < GRADUATION_NET_BOUGHT:
            raise gl.vm.UserError(
                "[EXPECTED] Graduation needs net buys of 85000000 microGEN, has "
                + str(net_bought)
            )
        listing.fill_pct_bp = str(_fill_pct_bp(_parse_int(listing.sold_tokens, "sold_tokens")))
        listing.status = STATUS_GRADUATED
        self._save_listing(listing)
        return listing.fill_pct_bp

    # ------------------------------------------------------------ views
    @gl.public.view
    def get_listing(self, listing_id: str) -> dict:
        return self._listing_dict(self._get_listing(listing_id))

    @gl.public.view
    def list_listings(self) -> dict:
        out = {}
        total = int(self.next_listing_id)
        for n in range(1, total):
            listing_id = str(n)
            if listing_id in self.listings:
                out[listing_id] = self._listing_dict(self.listings[listing_id])
        return out

    @gl.public.view
    def get_price(self, listing_id: str) -> str:
        listing = self._get_listing(listing_id)
        gen_reserve = _parse_int(listing.gen_reserve, "gen_reserve")
        token_reserve = _parse_int(listing.token_reserve, "token_reserve")
        return str(gen_reserve * MICRO_PER_GEN // token_reserve)

    @gl.public.view
    def get_leaderboard(self) -> list:
        rows = []
        total = int(self.next_listing_id)
        for n in range(1, total):
            listing_id = str(n)
            if listing_id not in self.listings:
                continue
            listing = self.listings[listing_id]
            rows.append(
                {
                    "id": listing.id,
                    "name": listing.name,
                    "symbol": listing.symbol,
                    "status": listing.status,
                    "price": str(
                        _parse_int(listing.gen_reserve, "gen_reserve")
                        * MICRO_PER_GEN
                        // _parse_int(listing.token_reserve, "token_reserve")
                    ),
                    "fill_pct_bp": listing.fill_pct_bp,
                    "net_bought": listing.net_bought,
                    "sold_tokens": listing.sold_tokens,
                }
            )
        rows.sort(key=lambda r: int(r["fill_pct_bp"]), reverse=True)
        return rows

    @gl.public.view
    def get_gen_balance(self, address: str) -> str:
        return str(self._gen_balance_of(Address(address)))

    @gl.public.view
    def get_token_balance(self, listing_id: str, address: str) -> str:
        return str(self._token_balance_of(listing_id, Address(address).as_hex))
