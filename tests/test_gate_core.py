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


def test_numeric_identifiers():
    # identifier/ordinal integers are NOT required quantities (verified_recall fix)
    check("salient: 'version 1' identifier dropped", anchors._salient_nums("QUIC version 1 uses TLS") == set())
    check("salient: decimal kept", "1.3" in anchors._salient_nums("uses TLS version 1.3 or greater"))
    check("salient: 'version 1' dropped but 1.3 kept",
          anchors._salient_nums("QUIC version 1 uses TLS version 1.3") == {"1.3"})
    check("salient: HTTP/3 identifier dropped", anchors._salient_nums("HTTP/3 runs over QUIC") == set())
    check("salient: 'Section 12' dropped", anchors._salient_nums("see Section 12 of the Act") == set())
    check("salient: 'RFC 9114' dropped", anchors._salient_nums("per RFC 9114") == set())
    check("salient: year kept", anchors._salient_nums("filed in 2026") == {"2026"})
    check("salient: percent kept", anchors._salient_nums("rose 8%") == {"8"})
    check("salient: currency kept", anchors._salient_nums("fined $500 million") == {"500"})
    check("salient: multi-digit count kept", anchors._salient_nums("analyzed 3000000 records") == {"3000000"})
    check("salient: bare single digit dropped", anchors._salient_nums("the 3 studies agree") == set())

    # the e2e regression: claim with stray 'version 1' identifier now anchors to a
    # span lacking a standalone '1' (the t6 false-negative we just fixed)
    claim = "QUIC version 1 uses TLS version 1.3 or greater as its handshake protocol."
    span = "An endpoint MUST terminate the connection if a version of TLS older than 1.3 is negotiated."
    check("numeric_ok: identifier no longer breaks anchor (t6 fix)", anchors.numeric_ok(claim, span))
    # number-swap still caught: claim 1.2 not in a 1.3 span
    check("numeric_ok: 1.2 vs 1.3 swap still caught",
          not anchors.numeric_ok("QUIC requires TLS version 1.2 or greater.", "older than 1.3"))


def test_numeric_scale_and_referent():
    # SCALE: same digits, different magnitude -> mismatch (literal anchor missed this)
    check("scale: $4.2bn != $4.2 million", not anchors.numeric_ok("revenue was $4.2 billion", "fell to $4.2 million"))
    check("scale: 4.2 billion ~ $4.2bn (currency-agnostic)", anchors.numeric_ok("revenue was 4.2 billion", "grew to $4.2bn"))
    check("scale: $115.2 billion ~ 115.2 billion", anchors.numeric_ok("rose to $115.2 billion", "a record 115.2 billion"))
    # PERCENT vs absolute: 8% != bare 8
    check("percent: 8% != bare 8", not anchors.numeric_ok("inflation rose 8%", "there were 8 members"))
    check("percent: 142% ~ 142%", anchors.numeric_ok("rose 142%", "up 142% year over year"))
    # _quantities normalization
    check("_quantities: $4.2bn -> mag 4.2e9", anchors._quantities("grew to $4.2bn") == {"mag:4200000000"})
    check("_quantities: 8% -> pct:8", anchors._quantities("rose 8%") == {"pct:8"})
    check("_quantities: 2026 -> year", anchors._quantities("in 2026") == {"year:2026"})

    # REFERENT flags (advisory — segment vs total, fiscal vs calendar)
    f = anchors.referent_flags("NVIDIA Data Center revenue was $130.5 billion",
                               "Total record full-year revenue was $130.5 billion")
    check("referent: data center vs total flagged", any(x["group"] == "scope" for x in f))
    f2 = anchors.referent_flags("fiscal 2025 revenue", "in calendar 2025")
    check("referent: fiscal vs calendar flagged", any(x["group"] == "fiscal_calendar" for x in f2))
    check("referent: no conflict -> empty", anchors.referent_flags("revenue rose", "revenue increased") == [])
    # referent flag is advisory: it does NOT fail anchors_ok on a literal match
    SNAP_R = "Total record full-year revenue was $130.5 billion."
    ok, d = anchors.anchors_ok("Total revenue was $130.5 billion", "Total record full-year revenue was $130.5 billion", SNAP_R)
    check("anchors_ok: referent_flags present in detail", "referent_flags" in d)


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
    test_numeric_identifiers()
    test_numeric_scale_and_referent()
    test_decide()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
