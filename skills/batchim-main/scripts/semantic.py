#!/usr/bin/env python3
"""semantic.py — 받침 semantic independence (PRD §6.2 FR-I1; M3, post-MVP).

M1 independence (`dedup.py`) collapses near-duplicates by canonical-URL + lexical
simhash. That misses **paraphrased syndication** — two sources that retell the
same wire story in different words are provenance-DEPENDENT but lexically far, so
simhash leaves them in distinct clusters and they can fake "≥2 independent
sources". M3 upgrades the signal with embeddings: sources whose content is
semantically near-duplicate are merged, distinguishing content near-dup from
genuine provenance independence.

NFR-5 degradation: a real embedding backend is used when available (passed in);
otherwise a **deterministic lexical-fallback embedder** (no network, reproducible)
is used and recorded, so the pipeline never hard-depends on a model server.
"""

import hashlib
import math
import re

_WORD = re.compile(r"\w+", re.UNICODE)
DIM = 256
DEFAULT_THRESHOLD = 0.80   # cosine ≥ this ⇒ semantic near-dup (paraphrase-level);
# calibrated on the lexical fallback: paraphrase ~0.84, unrelated ≤0.35. A real
# embedding backend would pass its own threshold.


def lexical_embed(text):
    """Deterministic bag-of-(word + char-3gram) hashed into a fixed-dim L2-normalized
    vector. A network-free stand-in for a real embedder (NFR-5 fallback): captures
    lexical-semantic overlap well enough to catch paraphrase, fully reproducible."""
    vec = [0.0] * DIM
    toks = _WORD.findall((text or "").lower())
    feats = list(toks)
    for t in toks:
        feats.extend(t[i:i + 3] for i in range(len(t) - 2))
    for f in feats:
        h = int(hashlib.sha1(f.encode("utf-8")).hexdigest(), 16)
        vec[h % DIM] += 1.0
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b))   # inputs are L2-normalized


def _source_text(s):
    return s.get("text") or s.get("snippet") or s.get("title") or ""


def embed_sources(sources, embedder=None):
    embedder = embedder or lexical_embed
    return {s["id"]: embedder(_source_text(s)) for s in sources}


def semantic_refine(clusters, sources, threshold=DEFAULT_THRESHOLD, embedder=None,
                    backend="lexical-fallback"):
    """Refine a lexical `independence_partition` with semantic near-dup merges.
    `clusters`: source_id → cluster_id (from dedup.py). Returns (new_clusters, info).
    Deterministic: stable union-find (lower source_id is root), relabel in sorted
    order. Existing lexical merges are preserved; only additional semantic merges
    are added (independence can only TIGHTEN, never split)."""
    embs = embed_sources(sources, embedder)
    ids = sorted(embs)
    parent = {i: i for i in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)   # stable: lower id wins

    # preserve existing lexical clusters
    by_lex = {}
    for sid, c in clusters.items():
        if sid in parent:
            by_lex.setdefault(c, []).append(sid)
    for grp in by_lex.values():
        for s in grp[1:]:
            union(grp[0], s)

    # additional semantic merges
    merges = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            if find(a) != find(b) and cosine(embs[a], embs[b]) >= threshold:
                union(a, b)
                merges.append({"a": a, "b": b, "cosine": round(cosine(embs[a], embs[b]), 4)})

    roots = sorted({find(i) for i in ids})
    label = {r: f"cl_{k:04d}" for k, r in enumerate(roots)}
    new = {i: label[find(i)] for i in ids}
    info = {
        "backend": backend, "threshold": threshold,
        "clusters_before": len(set(clusters.values())),
        "clusters_after": len(roots),
        "semantic_merges": merges,
    }
    return new, info


def main():
    import argparse, json, os
    p = argparse.ArgumentParser(description="받침 semantic independence refine (M3, FR-I1)")
    p.add_argument("--session", required=True)
    p.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = p.parse_args()
    art = os.path.join(args.session, "artifacts")
    sources = []
    with open(os.path.join(args.session, "sources", "sources.jsonl"), encoding="utf-8") as f:
        for line in f:
            if line.strip():
                sources.append(json.loads(line))
    part = json.load(open(os.path.join(art, "independence_partition.json"), encoding="utf-8"))
    new, info = semantic_refine(part.get("clusters", {}), sources, args.threshold)
    part["clusters"] = new
    part["dedup_version"] = "0.2.0-m3"
    part["semantic"] = info
    tmp = os.path.join(art, "independence_partition.json") + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(part, f, ensure_ascii=False, indent=2)
    os.replace(tmp, os.path.join(art, "independence_partition.json"))
    print(f"semantic: {info['clusters_before']} -> {info['clusters_after']} clusters "
          f"({len(info['semantic_merges'])} semantic merges, backend={info['backend']})")


if __name__ == "__main__":
    main()
