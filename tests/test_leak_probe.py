#!/usr/bin/env python3
"""Tests for bench/leak_probe.py — the false-entail (leak) probe. Locks the core
받침 invariant: adversarial WRONG high-risk claims do NOT reach `verified`, and the
panel is load-bearing for quote-mining. Run: python tests/test_leak_probe.py"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bench"))
import leak_probe as lp  # noqa: E402

P = F = 0


def check(name, cond):
    global P, F
    if cond:
        P += 1
    else:
        F += 1
        print(f"  FAIL: {name}")


FIX = os.path.join(os.path.dirname(__file__), "..", "bench", "adversarial", "leak_claims.jsonl")


def test_zero_leak():
    records = [lp.evaluate_claim(r) for r in lp._read_jsonl(FIX)]
    s = lp.summarize(records)
    check("leak_rate == 0.0 (no wrong claim verified)", s["leak_rate"] == 0.0)
    check("no leaks listed", s["leaks"] == [])
    check("headline n >= 6", s["headline_n"] >= 6)


def test_each_stratum_blocked_by_expected_mechanism():
    recs = {r["claim_id"]: lp.evaluate_claim(r) for r in lp._read_jsonl(FIX)}
    expect = {
        "l_fabrication": "anchor:span",
        "l_number_swap": "anchor:numeric",
        "l_number_nearmiss": "anchor:numeric",  # 0.53% swap > 0.05% tolerance -> still blocked
        "l_scale_swap": "anchor:numeric",
        "l_percent_swap": "anchor:numeric",
        "l_polarity_flip": "anchor:polarity",
        "l_version_swap": "anchor:numeric",   # ver-class conflict still catches a version swap
        "l_quote_mine": "panel:contradicts",  # anchors pass; only the panel blocks
    }
    for cid, cause in expect.items():
        r = recs[cid]
        check(f"{cid}: blocked (not leaked)", not r["leaked"])
        check(f"{cid}: blocked_by == {cause}", r["blocked_by"] == cause)


def test_anchor_strata_block_even_with_fooled_panel():
    # the deterministic guarantee: anchor strata block even when verifier AND panel
    # are adversarially set to entails.
    recs = {r["claim_id"]: r for r in lp._read_jsonl(FIX)}
    for cid in ("l_fabrication", "l_number_swap", "l_number_nearmiss", "l_scale_swap",
                "l_percent_swap", "l_polarity_flip", "l_version_swap"):
        check(f"{cid}: panel set to entails (fooled) in fixture", recs[cid].get("panel") == "entails")
        out = lp.evaluate_claim(recs[cid])
        check(f"{cid}: still blocked despite fooled panel", not out["leaked"])


def test_panel_is_load_bearing():
    # the quote-mine LEAKS once the panel is disabled -> panel necessity is proven.
    records = [lp.evaluate_claim(r) for r in lp._read_jsonl(FIX)]
    demo = lp.summarize(records)["panel_necessity_demo"]
    check("a panel-necessity demo row exists", len(demo) == 1)
    check("quote-mine leaks WITHOUT the panel", demo[0]["leaked_without_panel"] is True)


if __name__ == "__main__":
    test_zero_leak()
    test_each_stratum_blocked_by_expected_mechanism()
    test_anchor_strata_block_even_with_fooled_panel()
    test_panel_is_load_bearing()
    print(f"\n{P} passed, {F} failed")
    sys.exit(1 if F else 0)
