#!/usr/bin/env python3
"""Tests for bench/independence_probe.py — locks the independence-partition invariant
that decide.py depends on: syndicated/duplicated sources collapse to ONE cluster (no
fake independence), genuinely independent sources stay distinct (no over-merge), and
the paraphrase-without-provenance gap is a backend-quality issue (closed by a real
embedder). Run: python tests/test_independence_probe.py"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bench"))
import independence_probe as ip  # noqa: E402

P = F = 0


def check(name, cond):
    global P, F
    if cond:
        P += 1
    else:
        F += 1
        print(f"  FAIL: {name}")


FIX = os.path.join(os.path.dirname(__file__), "..", "bench", "adversarial", "independence_claims.jsonl")


def _records():
    return {r["scenario_id"]: r for r in (ip.evaluate_scenario(s) for s in ip._read_jsonl(FIX))}


def test_no_fake_independence_on_deterministic_signals():
    recs = _records()
    scns = ip._read_jsonl(FIX)
    gap_real = {s["scenario_id"]: ip.evaluate_gap_with_real_embedder(s)
                for s in scns if s.get("demonstrates") == "embedding_backend_needed"}
    s = ip.summarize(list(recs.values()), gap_real)
    check("fake_independence_rate == 0.0", s["fake_independence_rate"] == 0.0)
    check("no manufactured verified", s["manufactured_verify"] == [])
    check("over_merge_rate == 0.0", s["over_merge_rate"] == 0.0)


def test_each_deterministic_collapse():
    recs = _records()
    for sid in ("ip_canonical_url", "ip_verbatim_syndication", "ip_same_wire",
                "ip_same_byline", "ip_paraphrase_with_wire"):
        r = recs[sid]
        check(f"{sid}: collapses to 1 cluster", r["n_clusters"] == 1 and r["pass"])
        check(f"{sid}: cannot manufacture verified", not r.get("manufactured_verify"))


def test_genuine_independence_preserved():
    recs = _records()
    for sid in ("ip_independent_distinct", "ip_primary_plus_analysis"):
        r = recs[sid]
        check(f"{sid}: stays distinct", r["n_clusters"] == r["n_sources"] and r["pass"])
        check(f"{sid}: genuine independence enables verify", r["genuine_verify"] is True)


def test_paraphrase_gap_is_backend_quality():
    # the residual gap: the lexical fallback fakes independence on bare paraphrase,
    # but a real embedding backend collapses it (so it's a backend choice, not a bug).
    scns = ip._read_jsonl(FIX)
    demo = next(s for s in scns if s.get("demonstrates") == "embedding_backend_needed")
    rec = ip.evaluate_scenario(demo)
    check("gap: fallback FAILS to collapse bare paraphrase", rec["fake_independence"] is True)
    check("gap: a real embedder DOES collapse it", ip.evaluate_gap_with_real_embedder(demo) is True)


if __name__ == "__main__":
    test_no_fake_independence_on_deterministic_signals()
    test_each_deterministic_collapse()
    test_genuine_independence_preserved()
    test_paraphrase_gap_is_backend_quality()
    print(f"\n{P} passed, {F} failed")
    sys.exit(1 if F else 0)
