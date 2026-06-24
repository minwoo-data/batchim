#!/usr/bin/env python3
"""Tests for 받침 contrary.py (contrary-retrieval lens helper). Run: python tests/test_contrary.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "batchim-main", "scripts"))
import contrary  # noqa: E402

P = F = 0


def check(name, cond):
    global P, F
    if cond:
        P += 1
    else:
        F += 1
        print(f"  FAIL: {name}")


CLAIM = "The EU AI Act bans real-time biometric identification in publicly accessible spaces."


def test_queries():
    qs = contrary.generate_refutation_queries(CLAIM)
    check("queries: fact-check phrasing first", qs[0].startswith("is it true that"))
    check("queries: an exceptions/limitations query", any("exceptions" in q for q in qs))
    check("queries: key terms present (biometric)", any("biometric" in q for q in qs))
    check("queries: stopwords dropped (no bare 'the'/'real'/'time')",
          all("real time" not in q for q in qs))
    check("queries: capped + deduped", len(qs) == len(set(qs)) and len(qs) <= 10)
    check("queries: empty claim -> empty", contrary.generate_refutation_queries("") == [])


def test_aggregate():
    # nothing searched -> neutral (lens abstains, panel uses other lenses)
    check("aggregate: no findings -> neutral", contrary.aggregate([])["vote"] == "neutral")

    # a high-grade refutation -> contradicts
    r = contrary.aggregate([{"refutes": True, "quality_rating": "A", "summary": "Art 5 has exceptions"}])
    check("aggregate: A-grade refute -> contradicts", r["vote"] == "contradicts" and r["reason"] == "refuted")

    # a material qualifier the claim omits (quote-mine) -> contradicts
    r = contrary.aggregate([{"qualifies": True, "quality_rating": "B", "summary": "law-enforcement exception"}])
    check("aggregate: omitted qualifier -> contradicts", r["vote"] == "contradicts" and r["reason"] == "material_qualifier_omitted")

    # searched, found nothing contrary -> entails
    r = contrary.aggregate([{"refutes": False, "qualifies": False, "quality_rating": "A", "summary": "confirms"}])
    check("aggregate: no contrary found -> entails", r["vote"] == "entails")

    # a WEAK-grade refutation does not flip (conservative)
    r = contrary.aggregate([{"refutes": True, "quality_rating": "E", "summary": "a random forum post"}])
    check("aggregate: E-grade refute ignored -> entails", r["vote"] == "entails")

    # ungraded refutation counts (conservative toward quarantine)
    r = contrary.aggregate([{"refutes": True, "summary": "no grade"}])
    check("aggregate: ungraded refute -> contradicts", r["vote"] == "contradicts")

    # evidence summaries surfaced (capped at 3)
    r = contrary.aggregate([{"qualifies": True, "summary": f"f{i}"} for i in range(5)])
    check("aggregate: evidence capped at 3", len(r["evidence"]) == 3)


if __name__ == "__main__":
    test_queries()
    test_aggregate()
    print(f"\n{P} passed, {F} failed")
    sys.exit(1 if F else 0)
