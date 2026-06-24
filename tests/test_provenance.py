#!/usr/bin/env python3
"""Tests for 받침 provenance.py (FR-I1 provenance independence). Run: python tests/test_provenance.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "batchim-main", "scripts"))
import provenance as pv  # noqa: E402

P = F = 0


def check(name, cond):
    global P, F
    if cond:
        P += 1
    else:
        F += 1
        print(f"  FAIL: {name}")


def run():
    # two outlets carrying the SAME wire story -> provenance-dependent -> merge
    sources = [
        {"id": "s1", "wire": "Reuters", "byline": "By Jane Doe"},
        {"id": "s2", "wire": "Reuters", "byline": "By John Smith"},   # same wire
        {"id": "s3", "wire": None, "byline": "By Jane Doe"},          # same byline as s1
        {"id": "s4", "wire": None, "byline": "By Independent Author"},  # genuinely independent
    ]
    lexical = {"s1": "cl_0", "s2": "cl_1", "s3": "cl_2", "s4": "cl_3"}  # all distinct pre-provenance
    new, info = pv.provenance_refine(lexical, sources)
    check("same wire merged (s1==s2)", new["s1"] == new["s2"])
    check("same byline merged (s1==s3)", new["s1"] == new["s3"])
    check("independent source separate (s4)", new["s4"] != new["s1"])
    check("4 -> 2 clusters", info["clusters_after"] == 2)
    check("merges recorded with signal", any(m["signal"] == "wire" for m in info["provenance_merges"]))

    # byline normalization: "By Jane Doe" == "jane doe" == "BY  Jane   Doe"
    s = [{"id": "a", "byline": "By Jane Doe"}, {"id": "b", "byline": "BY  jane   doe"}]
    n2, _ = pv.provenance_refine({"a": "x", "b": "y"}, s)
    check("byline normalized merge", n2["a"] == n2["b"])

    # no provenance signal -> unchanged
    s3 = [{"id": "a"}, {"id": "b"}]
    n3, i3 = pv.provenance_refine({"a": "x", "b": "y"}, s3)
    check("no signal -> stays separate", n3["a"] != n3["b"] and i3["provenance_merges"] == [])

    # only tightens: a prior merge is preserved
    n4, _ = pv.provenance_refine({"s1": "c0", "s2": "c0", "s3": "c1", "s4": "c2"}, sources)
    check("prior merge preserved", n4["s1"] == n4["s2"])

    # determinism
    n5, _ = pv.provenance_refine(lexical, sources)
    check("deterministic", n5 == new)


if __name__ == "__main__":
    run()
    print(f"\n{P} passed, {F} failed")
    sys.exit(1 if F else 0)
