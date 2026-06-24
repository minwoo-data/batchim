#!/usr/bin/env python3
"""retrieval.py — 받침 hybrid RAG retrieval (PRD §6.8 FR-R3; M3, post-MVP).

Ranks candidate passages for a query so the Retrieve phase surfaces the right
evidence. Pipeline: query expansion → hybrid (lexical BM25 + embedding cosine) →
cross-encoder rerank → top-k. NFR-5 degradation: a real embedding/reranker backend
is used when passed; otherwise deterministic, network-free fallbacks (BM25-lite +
the lexical embedder + a term-coverage reranker) keep retrieval working offline.

Retrieval is a *recall* aid, NOT the verification gate — every surfaced passage
still passes the entailment gate + anchors before any claim is verified.
"""

import collections
import math
import re

import semantic  # reuse the lexical-fallback embedder + cosine

_WORD = re.compile(r"\w+", re.UNICODE)


def _tok(s):
    return _WORD.findall((s or "").lower())


def expand_query(query):
    """Deterministic query expansion: the original, plus a key-term subset (drops
    very short stopword-like tokens) and a quoted exact-phrase variant. A real
    backend can replace this with model-generated paraphrases."""
    toks = _tok(query)
    key = [t for t in toks if len(t) > 3]
    variants = [query]
    if key and " ".join(key) != query.lower():
        variants.append(" ".join(key))
    if len(toks) > 1:
        variants.append(f'"{query}"')
    seen, out = set(), []
    for v in variants:
        if v not in seen:
            seen.add(v); out.append(v)
    return out


def bm25(query, docs, k1=1.5, b=0.75):
    """BM25-lite lexical scores over docs=[{id,text}] for a single query string."""
    n = len(docs)
    if n == 0:
        return []
    doc_toks = [_tok(d.get("text", "")) for d in docs]
    avgdl = sum(len(t) for t in doc_toks) / n
    df = collections.Counter()
    for t in doc_toks:
        df.update(set(t))
    q = set(_tok(query))
    scores = []
    for toks in doc_toks:
        tf = collections.Counter(toks)
        s = 0.0
        for term in q:
            if term not in tf:
                continue
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            denom = tf[term] + k1 * (1 - b + b * len(toks) / (avgdl or 1))
            s += idf * (tf[term] * (k1 + 1)) / denom
        scores.append(s)
    return scores


def _embed_scores(query, docs, embedder):
    qv = embedder(query)
    return [semantic.cosine(qv, embedder(d.get("text", ""))) for d in docs]


def _minmax(xs):
    lo, hi = min(xs), max(xs)
    if hi <= lo:
        return [0.0 for _ in xs]
    return [(x - lo) / (hi - lo) for x in xs]


def hybrid(query, docs, alpha=0.5, embedder=None):
    """Blend normalized BM25 (lexical) and embedding cosine (semantic). alpha=1.0
    pure semantic, 0.0 pure lexical. Returns scores aligned to docs."""
    embedder = embedder or semantic.lexical_embed
    lex = _minmax(bm25(query, docs))
    emb = _minmax(_embed_scores(query, docs, embedder))
    return [alpha * e + (1 - alpha) * l for l, e in zip(lex, emb)]


def _coverage_rerank(query, docs):
    """Deterministic cross-encoder stand-in: fraction of distinct query terms a doc
    contains (a cheap relevance signal a real cross-encoder would refine)."""
    q = set(_tok(query))
    if not q:
        return [0.0 for _ in docs]
    return [len(q & set(_tok(d.get("text", "")))) / len(q) for d in docs]


def retrieve(query, docs, top_k=5, alpha=0.5, embedder=None, reranker=None,
             expand=True):
    """Full pipeline. `reranker(query, docs)->scores` overrides the fallback
    term-coverage reranker. Returns (ranked, info). Ranked = [{id, score,
    hybrid, rerank}], best first. Deterministic given fallbacks."""
    if not docs:
        return [], {"backend": "none", "n": 0}
    queries = expand_query(query) if expand else [query]
    # hybrid score = max over expanded queries (recall-oriented)
    hy = [0.0] * len(docs)
    for q in queries:
        for i, s in enumerate(hybrid(q, docs, alpha, embedder)):
            hy[i] = max(hy[i], s)

    rr = reranker(query, docs) if reranker else _coverage_rerank(query, docs)
    # final = rerank-dominant, hybrid as tiebreak (rerank is the sharper signal)
    final = [0.7 * r + 0.3 * h for h, r in zip(hy, rr)]
    order = sorted(range(len(docs)), key=lambda i: (-final[i], docs[i].get("id", "")))
    ranked = [{"id": docs[i].get("id"), "score": round(final[i], 4),
               "hybrid": round(hy[i], 4), "rerank": round(rr[i], 4)} for i in order[:top_k]]
    info = {
        "backend": ("embedder:custom" if embedder else "lexical-fallback")
                   + ("+reranker:custom" if reranker else "+reranker:coverage"),
        "queries": queries, "n": len(docs), "alpha": alpha,
    }
    return ranked, info


def main():
    import argparse, json, os, sys
    p = argparse.ArgumentParser(description="받침 hybrid retrieval (M3, FR-R3)")
    p.add_argument("--query", required=True)
    p.add_argument("--docs", required=True, help="jsonl of {id,text}")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--alpha", type=float, default=0.5)
    args = p.parse_args()
    docs = []
    with open(args.docs, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                docs.append(json.loads(line))
    ranked, info = retrieve(args.query, docs, args.top_k, args.alpha)
    json.dump({"ranked": ranked, "info": info}, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
