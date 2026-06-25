#!/usr/bin/env python3
"""Tests for bench/verified_recall.py — the over-abstention (verified_recall) probe.
Runs the control fixture through the real anchors+decide and locks the headline
recall + per-cause attribution. Run: python tests/test_verified_recall.py"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bench"))
import verified_recall as vr  # noqa: E402

P = F = 0


def check(name, cond):
    global P, F
    if cond:
        P += 1
    else:
        F += 1
        print(f"  FAIL: {name}")


FIX = os.path.join(os.path.dirname(__file__), "..", "bench", "control", "control_claims.jsonl")


def test_headline_recall_perfect():
    records = [vr.evaluate_claim(r) for r in vr._read_jsonl(FIX)]
    s = vr.summarize(records)
    # every adequately-evidenced TRUE high-risk claim must verify (no over-rejection bug)
    check("headline verified_recall == 1.0", s["headline_verified_recall"] == 1.0)
    check("no headline misses", s["headline_misses"] == [])
    check("headline n >= 10 (control-heavy)", s["headline_n"] >= 10)


def test_diagnostics_isolate_one_cause_each():
    records = {r["claim_id"]: vr.evaluate_claim(r)
               for r in vr._read_jsonl(FIX)}
    # each diagnostic probe must over-reject (status != verified) for its labelled reason
    expect = {
        "d_single_primary": "independence:lt2_clusters",
        "d_syndicated": "independence:lt2_clusters",
        "d_paraphrase": "anchor:span",
        "d_panel_split": "panel:no_consensus",
        "d_polarity_fp": "anchor:polarity",
        "d_grade_floor": "independence:no_ab_grade",
    }
    for cid, cause in expect.items():
        rec = records[cid]
        check(f"{cid}: over-rejected", rec["status"] != "verified")
        check(f"{cid}: cause == {cause}", rec["cause"] == cause)


def test_evaluate_uses_real_anchors():
    # the harness must reflect the anchors fix: a version-decimal true claim verifies
    rec = vr.evaluate_claim({
        "claim_id": "x", "headline": True, "panel": "entails",
        "claim": "TLS 1.3 provides forward secrecy.",
        "refs": [
            {"source_id": "a", "grade": "A", "cluster": "ca", "verifier": "entails",
             "span": "all key exchange provides forward secrecy",
             "snapshot": "In TLS 1.3 all key exchange provides forward secrecy."},
            {"source_id": "b", "grade": "B", "cluster": "cb", "verifier": "entails",
             "span": "every handshake provides forward secrecy",
             "snapshot": "Here every handshake provides forward secrecy by design."},
        ]})
    check("real-anchors: version-decimal claim verifies", rec["status"] == "verified")


if __name__ == "__main__":
    test_headline_recall_perfect()
    test_diagnostics_isolate_one_cause_each()
    test_evaluate_uses_real_anchors()
    print(f"\n{P} passed, {F} failed")
    sys.exit(1 if F else 0)
