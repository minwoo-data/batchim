#!/usr/bin/env python3
"""Golden-fixture tests for 받침 gate core: anchors (Appendix B) + §6.7 decision
algorithm (every branch). PRD D5. Runs standalone: `python tests/test_gate_core.py`."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "skills", "batchim-main", "scripts"))
import anchors  # noqa: E402
import decide   # noqa: E402

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


# ---------- anchors / Appendix B ----------
SNAP = "The Act prohibits real‑time biometric ID, with law‑enforcement exceptions. Revenue grew to $4.2bn in 2026."

def test_anchors():
    # smart-dash + NBSP normalize and match
    m, s, e, occ = anchors.span_match("real-time biometric ID", SNAP)
    check("span_match: smart-dash normalized match", m)
    # paraphrase does not match
    m2, *_ = anchors.span_match("realtime biometric identification system", SNAP)
    check("span_match: paraphrase rejected", not m2)
    # fabricated quote rejected
    m3, *_ = anchors.span_match("a total nationwide ban with no exceptions", SNAP)
    check("span_match: fabricated quote rejected", not m3)
    # numeric anchor: claim number present in span
    check("numeric_ok: $4.2bn / 2026 present", anchors.numeric_ok("revenue was 4.2bn in 2026", "grew to $4.2bn in 2026"))
    # numeric anchor: number swap caught
    check("numeric_ok: swapped 5.0 not in span", not anchors.numeric_ok("revenue was 5.0bn", "grew to $4.2bn"))
    # no number in claim -> trivially ok
    check("numeric_ok: no numbers -> ok", anchors.numeric_ok("the act bans it", "anything"))
    # combined anchors_ok
    ok, d = anchors.anchors_ok("revenue grew to 4.2bn in 2026", "grew to $4.2bn in 2026", SNAP)
    check("anchors_ok: matched + numeric", ok and d["span_matched"] and d["numeric_ok"])


def T(verdict, anchors_ok=True, cluster="cl", grade="A", sid="s"):
    return {"normalized_verdict": verdict, "anchors_ok": anchors_ok,
            "cluster_id": cluster, "quality_rating": grade, "source_id": sid}


# ---------- §6.7 every branch ----------
def test_decide():
    # step 0: missing (no tuples) -> unresolved/missing
    r = decide.decide_claim("c", [])
    check("6.7-0 missing -> unresolved/missing", r["status"] == "unresolved" and r["status_reason"] == "missing")

    # step 0b: budget-skipped no tuples -> coverage_degraded
    r = decide.decide_claim("c", [], skipped_budget=True)
    check("6.7-0 skipped_budget flagged", r["coverage_degraded"] and r["status_reason"] == "skipped_budget")

    # step 1: structural -> raises
    try:
        decide.decide_claim("c", [{"structural_error": "orphan id"}])
        check("6.7-1 structural raises", False)
    except decide.StructuralError:
        check("6.7-1 structural raises", True)

    # step 2: A/B contradicts -> refuted (dominates coexisting entails)
    r = decide.decide_claim("c", [T("entails", cluster="a", sid="s1"),
                                   T("entails", cluster="b", sid="s2"),
                                   T("contradicts", grade="A", sid="s3")])
    check("6.7-2 A/B contradicts -> refuted (dominates)", r["status"] == "refuted" and r["refuted_by"] == ["s3"])

    # step 2: M2 panel overturns refutation
    r = decide.decide_claim("c", [T("entails", cluster="a", sid="s1"),
                                   T("entails", cluster="b", sid="s2"),
                                   T("contradicts", grade="A", sid="s3")],
                            m2_enabled=True, panel_consensus="entails")
    check("6.7-2 M2 panel overturns refutation -> verified", r["status"] == "verified")

    # step 3: conflict (entails + non-A/B contradicts) -> unresolved/conflict
    r = decide.decide_claim("c", [T("entails", cluster="a", sid="s1"),
                                   T("contradicts", grade="C", sid="s2")])
    check("6.7-3 conflict -> unresolved", r["status"] == "unresolved" and r["conflict"] and r["status_reason"] == "conflict")

    # step 4: verified (>=2 distinct clusters, >=1 A/B in entailing set), M1 (no panel)
    r = decide.decide_claim("c", [T("entails", cluster="a", grade="A", sid="s1"),
                                   T("entails", cluster="b", grade="C", sid="s2")])
    check("6.7-4 verified (M1)", r["status"] == "verified" and r["independent_entails"] == 2)

    # step 4 fail: two entails but SAME cluster (fake independence) -> unresolved
    r = decide.decide_claim("c", [T("entails", cluster="same", grade="A", sid="s1"),
                                   T("entails", cluster="same", grade="B", sid="s2")])
    check("6.7-4 same-cluster -> not verified", r["status"] == "unresolved")

    # step 4 fail: two distinct clusters but NO A/B in entailing set -> unresolved
    r = decide.decide_claim("c", [T("entails", cluster="a", grade="C", sid="s1"),
                                   T("entails", cluster="b", grade="D", sid="s2")])
    check("6.7-4 no A/B -> not verified", r["status"] == "unresolved")

    # step 4: anchor-failed entails counts as neutral -> not verified
    r = decide.decide_claim("c", [T("entails", anchors_ok=False, cluster="a", sid="s1"),
                                   T("entails", cluster="b", grade="A", sid="s2")])
    check("6.7 anchor-failed entails -> neutral -> not verified", r["status"] == "unresolved")

    # step 4 M2: distinct+A/B but panel no consensus -> unresolved/panel_no_consensus
    r = decide.decide_claim("c", [T("entails", cluster="a", grade="A", sid="s1"),
                                   T("entails", cluster="b", grade="C", sid="s2")],
                            m2_enabled=True, panel_consensus="neutral")
    check("6.7-4 M2 panel no consensus -> unresolved", r["status"] == "unresolved" and r["status_reason"] == "panel_no_consensus")

    # step 4 M2: distinct+A/B AND panel entails -> verified
    r = decide.decide_claim("c", [T("entails", cluster="a", grade="A", sid="s1"),
                                   T("entails", cluster="b", grade="C", sid="s2")],
                            m2_enabled=True, panel_consensus="entails")
    check("6.7-4 M2 panel consensus -> verified", r["status"] == "verified")

    # step 5: single entails -> unresolved/insufficient
    r = decide.decide_claim("c", [T("entails", cluster="a", sid="s1")])
    check("6.7-5 single entails -> unresolved", r["status"] == "unresolved" and r["status_reason"] == "insufficient_independent_entails")


if __name__ == "__main__":
    test_anchors()
    test_decide()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
