# Known limitations

- **Nominal TEST ledger.** GEN balances in this contract are an in-contract
  ledger, not real GEN. `claim_test_gen()` credits 1,000 GEN once per
  address for testing; buys and sells only move ledger entries. The
  contract never transfers real GEN.
- **Fees are ledger entries.** The 1% trade fee (0.3% creator, 0.7%
  platform pool) is recorded per listing in the contract. It is not paid
  out to any external address.
- **Graduation is an internal state change.** When a listing graduates,
  its status becomes `GRADUATED` and the curve locks. Tokens are not
  migrated to any external DEX and no liquidity pool is created.
- **Review judges validator-fetched source evidence.** At review time the
  leader and each validator independently fetch the listing's
  `evidence_source` URL and judge the fetched content together with the
  creator's statement. A source that cannot be fetched blocks the review.
  The source URL itself is creator-supplied, so this authenticates that
  the reviewed content came from the stated public source — it is not an
  independent check of real-world identity beyond that source.
- **Deterministic curve pricing.** Prices come only from the constant
  product curve. There is no external price feed.
- **First live review attempt.** The first deployment's first
  `review_listing` reached FINALIZED but validators disagreed after all
  rotations, so no state was written. The comparison was changed to
  strict equality on the decision token and the review prompt was
  corrected for self-statement evidence; the contract was then redeployed
  (current address). The attempt record is kept in
  `evidence/review-attempt-1.json`.
