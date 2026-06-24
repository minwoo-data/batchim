#!/usr/bin/env python3
"""Tests for 받침 semantic.py (FR-I1 semantic independence, M3). Run: python tests/test_semantic.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "batchim-main", "scripts"))
import semantic as sm  # noqa: E402

P = F = 0


def check(name, cond):
    global P, F
    if cond:
        P += 1
    else:
        F += 1
        print(f"  FAIL: {name}")


# lexically distinct but same wire story (paraphrase) -> provenance-dependent
A = "The agency approved the merger after a lengthy antitrust review."
B = "After a lengthy antitrust review, regulators approved the merger."
C = "Critics warned the deal would raise consumer prices sharply."   # independent angle
D = "NVIDIA data center revenue rose 142% to a record 115.2 billion dollars."  # different topic


def _srcs():
    return [{"id": "s1", "text": A}, {"id": "s2", "text": B},
            {"id": "s3", "text": C}, {"id": "s4", "text": D}]


def run():
    check("paraphrase cosine high (~0.84)", sm.cosine(sm.lexical_embed(A), sm.lexical_embed(B)) > 0.8)
    check("unrelated cosine low (<0.5)", sm.cosine(sm.lexical_embed(A), sm.lexical_embed(C)) < 0.5)

    # lexical dedup left all 4 in distinct clusters; semantic merges the paraphrase pair
    lexical = {"s1": "cl_0000", "s2": "cl_0001", "s3": "cl_0002", "s4": "cl_0003"}
    new, info = sm.semantic_refine(lexical, _srcs())
    check("paraphrase pair merged (s1==s2)", new["s1"] == new["s2"])
    check("independent angle stays separate (s3)", new["s3"] != new["s1"])
    check("different topic stays separate (s4)", new["s4"] != new["s1"] and new["s4"] != new["s3"])
    check("4 -> 3 clusters", info["clusters_after"] == 3 and info["clusters_before"] == 4)
    check("merge recorded with cosine", len(info["semantic_merges"]) == 1 and info["semantic_merges"][0]["cosine"] > 0.8)

    # determinism + stable labels
    new2, _ = sm.semantic_refine(lexical, _srcs())
    check("deterministic", new == new2)

    # independence only TIGHTENS: an existing lexical merge is preserved
    lex_merged = {"s1": "cl_0000", "s2": "cl_0000", "s3": "cl_0001", "s4": "cl_0002"}
    new3, _ = sm.semantic_refine(lex_merged, _srcs())
    check("preserves prior lexical merge", new3["s1"] == new3["s2"])

    # backend recorded (NFR-5)
    check("backend recorded", info["backend"] == "lexical-fallback")

    # pluggable backend: a custom embedder is honored
    def all_same(_t):
        return [1.0] + [0.0] * (sm.DIM - 1)
    n4, i4 = sm.semantic_refine({"s1": "a", "s2": "b", "s3": "c", "s4": "d"}, _srcs(),
                                embedder=all_same, backend="stub")
    check("custom embedder collapses all", i4["clusters_after"] == 1 and i4["backend"] == "stub")


if __name__ == "__main__":
    run()
    print(f"\n{P} passed, {F} failed")
    sys.exit(1 if F else 0)
