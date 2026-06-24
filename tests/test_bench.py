#!/usr/bin/env python3
"""Tests for 받침 measurement infra: kappa.py (Cohen's κ + gate) and
score_benchmark.py (false-entail / precision / recall). Run: python tests/test_bench.py"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bench"))
import kappa            # noqa: E402
import score_benchmark  # noqa: E402
import freeze           # noqa: E402
import json             # noqa: E402
import tempfile         # noqa: E402

P = F = 0


def check(name, cond):
    global P, F
    if cond:
        P += 1
    else:
        F += 1
        print(f"  FAIL: {name}")


def test_cohen_kappa():
    check("perfect agreement -> 1.0", kappa.cohen_kappa(["entails"] * 4, ["entails"] * 4) == 1.0)
    # a=[e,e,n,c] b=[e,n,n,c]: po=.75, pe=.3125 -> κ≈0.636
    k = kappa.cohen_kappa(["entails", "entails", "neutral", "contradicts"],
                          ["entails", "neutral", "neutral", "contradicts"])
    check("partial agreement κ≈0.636", abs(k - 0.6364) < 0.001)
    check("empty -> None", kappa.cohen_kappa([], []) is None)


def test_agreement_gate():
    L = {
        "alice": {"u1": "entails", "u2": "neutral", "u3": "contradicts", "u4": "entails"},
        "bob":   {"u1": "entails", "u2": "neutral", "u3": "contradicts", "u4": "entails"},
    }
    rep = kappa.agreement(L, threshold=0.7)
    check("identical labelers -> PASS", rep["gate"] == "PASS" and rep["min_kappa"] == 1.0)
    check("no disagreements", rep["n_disagreements"] == 0)

    L["bob"]["u2"] = "entails"; L["bob"]["u4"] = "neutral"  # introduce disagreement
    rep = kappa.agreement(L, threshold=0.7)
    check("disagreement -> FAIL gate (<0.7)", rep["gate"] == "FAIL")
    check("disagreements listed for adjudication", "u2" in rep["disagreements"] and "u4" in rep["disagreements"])


def test_score():
    system = {"c1": "verified", "c2": "verified", "c3": "unresolved", "c4": "verified"}
    gold = {"c1": "verified", "c2": "unresolved", "c3": "verified", "c4": "verified"}
    strata = {"c1": "control", "c2": "quote-mining", "c3": "fabrication", "c4": "control"}
    rep = score_benchmark.score(system, gold, strata)
    o = rep["overall"]
    check("false-entail total = 1 (c2)", o["false_entail_total"] == 1)
    check("false-neg total = 1 (c3)", o["false_neg_total"] == 1)
    check("precision = 2/3", abs(o["precision"] - 0.6667) < 0.001)  # tp=2 (c1,c4), fp=1 (c2)
    check("recall = 2/3", abs(o["recall"] - 0.6667) < 0.001)        # tp=2, fn=1 (c3)
    by = rep["by_stratum"]
    check("quote-mining stratum has the false-entail", by["quote-mining"]["false_entail"] == 1)
    check("fabrication stratum has the false-neg", by["fabrication"]["false_neg"] == 1)


def test_freeze():
    d = tempfile.mkdtemp(prefix="batchim_freeze_")
    os.makedirs(os.path.join(d, "labels"))
    json.dump({"topics": [1, 2]}, open(os.path.join(d, "topics.json"), "w"))
    json.dump({"min_kappa": 0.7, "margin": 0.05}, open(os.path.join(d, "thresholds.json"), "w"))
    with open(os.path.join(d, "labels", "gold.jsonl"), "w") as f:
        f.write(json.dumps({"unit_id": "c::s", "label": "entails"}) + "\n")

    m = freeze.build(d, frozen_at="2026-06-24")
    json.dump(m, open(os.path.join(d, "bench_manifest.json"), "w"), sort_keys=True)
    check("freeze: all three hashes present",
          all(m[k] and m[k].startswith("sha256:") for k in ("topic_set_hash", "threshold_hash", "label_set_hash")))
    check("freeze: signature present", str(m.get("signature", "")).startswith("sha256:"))

    ok, diffs = freeze.verify(d)
    check("freeze verify clean -> ok", ok and not diffs)

    # tamper a topic after freezing -> drift detected (no goalpost-moving)
    json.dump({"topics": [1, 2, 3]}, open(os.path.join(d, "topics.json"), "w"))
    ok, diffs = freeze.verify(d)
    check("freeze verify post-edit -> drift", not ok and any("topic_set_hash" in x for x in diffs))


if __name__ == "__main__":
    test_cohen_kappa()
    test_agreement_gate()
    test_score()
    test_freeze()
    print(f"\n{P} passed, {F} failed")
    sys.exit(1 if F else 0)
