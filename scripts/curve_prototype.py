# Pure-Python mirror of the bonding-curve math in contracts/meme_launchpad.py.
# No GenLayer dependency: run with plain `python3 scripts/curve_prototype.py`.
# Every amount is an integer; microGEN is the GEN unit (1 GEN = 1_000_000 microGEN)
# and tokens use smallest units with precision 0 (1 token = 1 unit).
# No floats anywhere in this file.

MICRO_PER_GEN = 1_000_000

TOTAL_SUPPLY = 1_000_000_000       # tokens, smallest units, precision 0
CURVE_SUPPLY = 793_100_000         # tokens sold along the curve
GRADUATION_RESERVE = 206_900_000   # tokens held back for graduation (not on the curve)

GEN_RESERVE0 = 30_000_000          # 30 GEN, virtual GEN reserve (microGEN)
TOKEN_RESERVE0 = CURVE_SUPPLY      # virtual token reserve (smallest units)
K = GEN_RESERVE0 * TOKEN_RESERVE0  # constant product

FEE_NUM = 1                        # 1% total fee
FEE_DEN = 100
CREATOR_FEE_SHARE_NUM = 30         # 30% of the fee goes to the creator
CREATOR_FEE_SHARE_DEN = 100        # remaining 70% goes to the platform pool

GRADUATION_NET_BOUGHT = 85_000_000  # 85 GEN net buys trigger graduation
CLAIM_AMOUNT = 1_000 * MICRO_PER_GEN  # 1000 GEN test credit per address


def price(gen_reserve: int, token_reserve: int) -> int:
    """microGEN per token, scaled by 1_000_000 (integer)."""
    assert gen_reserve > 0 and token_reserve > 0
    return gen_reserve * MICRO_PER_GEN // token_reserve


def fill_pct_bp(sold_tokens: int) -> int:
    """Curve-sold share of CURVE_SUPPLY, in basis points of a percent (7391 = 73.91%)."""
    return sold_tokens * 10_000 // CURVE_SUPPLY


def split_fee(fee: int) -> tuple[int, int]:
    creator_fee = fee * CREATOR_FEE_SHARE_NUM // CREATOR_FEE_SHARE_DEN
    platform_fee = fee - creator_fee
    return creator_fee, platform_fee


def buy(gen_reserve: int, token_reserve: int, amount_micro: int):
    """Return (new_gen, new_token, tokens_out, fee, creator_fee, platform_fee)."""
    assert amount_micro > 0
    fee = amount_micro * FEE_NUM // FEE_DEN
    net = amount_micro - fee
    new_gen = gen_reserve + net
    new_token = K // new_gen
    tokens_out = token_reserve - new_token
    assert tokens_out > 0, "buy too small to move the curve"
    assert new_token > 0
    creator_fee, platform_fee = split_fee(fee)
    assert creator_fee + platform_fee == fee
    return new_gen, new_token, tokens_out, fee, creator_fee, platform_fee


def sell(gen_reserve: int, token_reserve: int, token_amount: int):
    """Return (new_gen, new_token, gross_gen, net_gen, fee, creator_fee, platform_fee)."""
    assert token_amount > 0
    new_token = token_reserve + token_amount
    new_gen = K // new_token
    gross = gen_reserve - new_gen
    assert gross > 0, "sell too small to move the curve"
    fee = gross * FEE_NUM // FEE_DEN
    net_gen = gross - fee
    creator_fee, platform_fee = split_fee(fee)
    assert creator_fee + platform_fee == fee
    return new_gen, new_token, gross, net_gen, fee, creator_fee, platform_fee


def main() -> None:
    gen, tok = GEN_RESERVE0, TOKEN_RESERVE0
    sold = 0
    net_bought = 0
    creator_fees = 0
    platform_fees = 0

    p0 = price(gen, tok)
    print(f"initial price: {p0} microGEN/token (scaled 1e6) = {p0 / 1_000_000:.6f} microGEN/token")
    assert p0 == 37_826, p0
    assert isinstance(p0, int) and not isinstance(p0, float)

    # --- Test vector 1: a 1 GEN buy pushes the price up ---
    gen, tok, out, fee, cf, pf = buy(gen, tok, 1 * MICRO_PER_GEN)
    sold += out
    net_bought += 1 * MICRO_PER_GEN - fee
    creator_fees += cf
    platform_fees += pf
    p1 = price(gen, tok)
    print(f"buy 1 GEN -> {out} tokens, fee {fee} microGEN "
          f"(creator {cf}, platform {pf}), price {p0} -> {p1}")
    assert out == 25_336_206, out
    assert fee == 10_000 and cf == 3_000 and pf == 7_000
    assert p1 > p0, "buy must push the price up"
    assert isinstance(out, int)

    # --- Test vector 2: selling part of it back pushes the price down ---
    sell_amount = out // 2
    gen, tok, gross, net_gen, fee, cf, pf = sell(gen, tok, sell_amount)
    sold -= sell_amount
    net_bought -= net_gen
    creator_fees += cf
    platform_fees += pf
    p2 = price(gen, tok)
    print(f"sell {sell_amount} tokens -> {net_gen} microGEN net "
          f"(gross {gross}, fee {fee}: creator {cf}, platform {pf}), price {p1} -> {p2}")
    assert p2 < p1, "sell must push the price down"
    assert p2 > p0, "price stays above start after a round trip (fees + curve)"

    # --- Test vector 3: fee split always adds up, over many trades ---
    for amt in (500_000, 2_000_000, 123_456, 10_000_000):
        g2, t2, o, f, c, pl = buy(gen, tok, amt)
        assert c + pl == f and f == amt // 100
        gen, tok = g2, t2
        sold += o
        net_bought += amt - f
        creator_fees += c
        platform_fees += pl
    print(f"after extra buys: net_bought={net_bought} microGEN, "
          f"fees creator={creator_fees} platform={platform_fees}")

    # --- Test vector 4: repeated 10 GEN buys reach graduation ---
    buys = 0
    while net_bought < GRADUATION_NET_BOUGHT:
        gen, tok, out, fee, cf, pf = buy(gen, tok, 10 * MICRO_PER_GEN)
        sold += out
        net_bought += 10 * MICRO_PER_GEN - fee
        creator_fees += cf
        platform_fees += pf
        buys += 1
        assert buys < 50, "graduation should be reachable in a few buys"
    fill = fill_pct_bp(sold)
    p3 = price(gen, tok)
    print(f"graduation reached after {buys} x 10 GEN buys: "
          f"net_bought={net_bought} microGEN (>= {GRADUATION_NET_BOUGHT}), "
          f"sold={sold} tokens, fill={fill} bp = {fill / 100:.2f}%, price={p3}")
    assert net_bought >= GRADUATION_NET_BOUGHT
    # Fill at graduation depends on the path: exactly 85 GEN net with no
    # prior trades sells 586,204,348 tokens (73.91%); this path overshoots
    # the threshold by ~7 GEN because buys come in 10 GEN steps.
    assert 7_300 <= fill <= 7_600, fill
    assert sold <= CURVE_SUPPLY
    assert tok == TOKEN_RESERVE0 - sold
    assert tok > 0 and gen > GEN_RESERVE0

    # --- Test vector 5: a 1000 GEN claim covers the whole graduation path ---
    spent = 1 * MICRO_PER_GEN + 500_000 + 2_000_000 + 123_456 + 10_000_000 + buys * 10 * MICRO_PER_GEN
    assert spent < CLAIM_AMOUNT, (spent, CLAIM_AMOUNT)
    print(f"total GEN spent on the graduation path: {spent} microGEN "
          f"(< claim {CLAIM_AMOUNT})")

    # --- Test vector 6: boundary behaviour ---
    # Any positive buy yields >= 1 token: K // new_gen < K / gen == token
    # reserve whenever net > 0, so there is no dust-buy failure mode.
    # A 1 microGEN buy at genesis yields exactly 27 tokens.
    g0, t0, o0, _, _, _ = buy(GEN_RESERVE0, TOKEN_RESERVE0, 1)
    assert o0 == 27, o0
    print("1 microGEN buy at genesis -> 27 tokens (no dust failure mode)")
    # Zero / negative amounts must fail.
    for bad in (0, -5):
        try:
            buy(gen, tok, bad)
        except AssertionError:
            print(f"buy({bad}) correctly rejected")
        else:
            raise AssertionError(f"buy({bad}) must fail")
        try:
            sell(gen, tok, bad)
        except AssertionError:
            print(f"sell({bad}) correctly rejected")
        else:
            raise AssertionError(f"sell({bad}) must fail")

    print("ALL CURVE PROTOTYPE ASSERTIONS PASSED")


if __name__ == "__main__":
    main()
