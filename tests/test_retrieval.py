#!/usr/bin/env python3
"""Tests for 받침 retrieval.py (FR-R3 hybrid RAG). Run: python tests/test_retrieval.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "batchim-main", "scripts"))
import retrieval as rt  # noqa: E402

P = F = 0


def check(name, cond):
    global P, F
    if cond:
        P += 1
    else:
        F += 1
        print(f"  FAIL: {name}")


Q = "EU AI Act ban on real-time biometric identification"
DOCS = [
    {"id": "d1", "text": "The EU AI Act prohibits real-time remote biometric identification in publicly accessible spaces."},
    {"id": "d2", "text": "Brussels' new artificial intelligence regulation restricts live facial recognition biometric surveillance."},
    {"id": "d3", "text": "NVIDIA data center revenue rose 142 percent to a record 115.2 billion dollars in fiscal 2025."},
]


def _rank_ids(ranked):
    return [r["id"] for r in ranked]


def run():
    # query expansion: original + key-term subset + quoted phrase
    ex = rt.expand_query(Q)
    check("expand: includes original", Q in ex)
    check("expand: produces variants", len(ex) >= 2)

    # bm25: the on-topic doc outscores the off-topic one
    lex = rt.bm25(Q, DOCS)
    check("bm25: d1 > d3", lex[0] > lex[2])

    # full retrieve: d1 first, d3 last; semantic d2 beats off-topic d3
    ranked, info = rt.retrieve(Q, DOCS, top_k=3)
    ids = _rank_ids(ranked)
    check("retrieve: d1 ranked first", ids[0] == "d1")
    check("retrieve: d3 ranked last", ids[-1] == "d3")
    check("retrieve: semantic d2 beats off-topic d3", ids.index("d2") < ids.index("d3"))
    check("retrieve: backend recorded (NFR-5 fallback)", "lexical-fallback" in info["backend"])

    # top_k limits results
    top1, _ = rt.retrieve(Q, DOCS, top_k=1)
    check("top_k=1 returns one", len(top1) == 1 and top1[0]["id"] == "d1")

    # deterministic
    r2, _ = rt.retrieve(Q, DOCS, top_k=3)
    check("deterministic", _rank_ids(r2) == ids)

    # pluggable reranker is honored (force d3 to the top)
    def boost_d3(query, docs):
        return [1.0 if d["id"] == "d3" else 0.0 for d in docs]
    rr, info2 = rt.retrieve(Q, DOCS, top_k=3, reranker=boost_d3)
    check("custom reranker honored", _rank_ids(rr)[0] == "d3" and "reranker:custom" in info2["backend"])

    # pluggable embedder honored + alpha=1.0 (pure semantic)
    ranked_sem, info3 = rt.retrieve(Q, DOCS, top_k=3, alpha=1.0)
    check("pure-semantic still ranks d1 top", _rank_ids(ranked_sem)[0] == "d1")

    # empty corpus
    empty, ei = rt.retrieve(Q, [], top_k=3)
    check("empty docs -> []", empty == [] and ei["n"] == 0)


if __name__ == "__main__":
    run()
    print(f"\n{P} passed, {F} failed")
    sys.exit(1 if F else 0)
