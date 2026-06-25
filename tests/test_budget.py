#!/usr/bin/env python3
"""Tests for 받침 budget.py (FR-P2 reserve-before-dispatch). Run: python tests/test_budget.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "batchim-main", "scripts"))
import budget  # noqa: E402

P = F = 0


def check(name, cond):
    global P, F
    if cond:
        P += 1
    else:
        F += 1
        print(f"  FAIL: {name}")


def run():
    b = budget.Budget(3)
    check("reserve within budget", b.reserve() and b.reserve() and b.reserve())
    check("spent == 3", b.spent() == 3 and b.remaining() == 0)
    check("over-budget reserve denied", not b.reserve())
    check("denied -> exhausted flag", b.exhausted)

    # reserve-before-dispatch: a multi-slot reserve is all-or-nothing (no partial spend)
    b2 = budget.Budget(2)
    check("can't reserve 3 of 2 (no partial)", not b2.reserve(3) and b2.remaining() == 2)
    check("can reserve 2 of 2", b2.reserve(2) and b2.remaining() == 0)

    # the over-dispatch race: with budget=1, only ONE of two 'workers' may proceed
    b3 = budget.Budget(1)
    w1, w2 = b3.reserve(), b3.reserve()
    check("budget=1 -> exactly one worker dispatches", (w1, w2) == (True, False))

    # release returns slots but never exceeds total
    b4 = budget.Budget(1)
    b4.reserve(); b4.release(); b4.release()
    check("release capped at total", b4.remaining() == 1)

    check("concurrency clamped to MAX_CONCURRENT", budget.cap_concurrency(16) == budget.MAX_CONCURRENT)
    check("concurrency floor 1", budget.cap_concurrency(0) == 1)
    check("caps present", budget.MAX_VERIFIER_CALLS == 120 and budget.MAX_SPANS_PER_CLAIM == 3)


def cost_model():
    # SANITY vs the informal smoke: 6 atomic high-risk claims, ~10 cited refs
    # (≈1.67 sources/claim), 3 verified-candidates reach the panel (frac 0.5).
    # The smoke ran 10 isolated verifiers + 3 lenses × 3 candidates = 9 panel calls.
    c = budget.estimate_calls(6, sources_per_claim=1.67, panel_candidate_frac=0.5)
    check("smoke: verifier_calls ~ 10", c["verifier_calls"] == 10)
    check("smoke: panel_candidates == 3", c["panel_candidates"] == 3)
    check("smoke: panel_calls == 9 (3 lenses x 3)", c["panel_calls"] == 9)
    check("smoke: total == 19", c["total_calls"] == 19)
    check("smoke: no caps hit", not c["verifier_capped"] and not c["panel_capped"])

    # caps engage on a large run -> completed-degraded flags
    big = budget.estimate_calls(60, sources_per_claim=3, panel_candidate_frac=1.0)
    check("big: verifier capped at 120", big["verifier_calls"] == budget.MAX_VERIFIER_CALLS and big["verifier_capped"])
    check("big: panel capped at 90", big["panel_calls"] == budget.MAX_PANEL_CALLS and big["panel_capped"])

    # tokens scale with calls; verifier input dominated by snapshot
    t = budget.estimate_tokens(c)
    expect_v_in = 10 * (600 + 60 + 1200)
    check("tokens: verifier_input = calls*(overhead+claim+snapshot)", t["verifier_input"] == expect_v_in)
    check("tokens: totals add up", t["total_tokens"] == t["input_tokens"] + t["output_tokens"])
    check("tokens: input > output (read-heavy)", t["input_tokens"] > t["output_tokens"])

    # cost: illustrative by default, exact when prices supplied
    m = budget.estimate_cost(t)
    check("cost: illustrative flag set on default price", m["illustrative"])
    m2 = budget.estimate_cost(t, price_in_per_mtok=3.0, price_out_per_mtok=15.0)
    expect_usd = round(t["input_tokens"] / 1e6 * 3.0 + t["output_tokens"] / 1e6 * 15.0, 4)
    check("cost: exact price -> not illustrative", not m2["illustrative"] and m2["usd"] == expect_usd)

    # zero-claim run costs nothing; one-shot bundle + formatter don't crash
    z = budget.estimate_run(0)
    check("zero claims -> $0", z["cost"]["usd"] == 0.0 and z["calls"]["total_calls"] == 0)
    est = budget.estimate_run(6, 1.67, 0.5)
    check("format_estimate returns a string", isinstance(budget.format_estimate(est), str) and "19" in budget.format_estimate(est))


if __name__ == "__main__":
    run()
    cost_model()
    print(f"\n{P} passed, {F} failed")
    sys.exit(1 if F else 0)
