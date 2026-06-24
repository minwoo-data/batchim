#!/usr/bin/env python3
"""provenance.py — 받침 provenance independence (PRD §6.2 FR-I1; M3).

Lexical (`dedup`) and semantic (`semantic`) merges catch content near-duplicates.
But two sources can be lexically AND semantically distinct yet provenance-DEPENDENT
— they redistribute the same wire story, or carry the same byline across outlets,
or were published in the same syndication burst. Counting them as "2 independent
sources" is the echo-chamber failure of independence. This refines the partition
with high-precision provenance signals so "≥2 independent" means *independent
origin*, not *independent URL*.

Signals (high precision — merge only on strong evidence of shared origin):
  - same `wire`     (e.g. "Reuters", "AP")           — identical syndicated content
  - same `byline`   (normalized author)              — one author, many outlets
  - same `published_at` minute + same `wire`/byline  — syndication burst

Independence only TIGHTENS (never splits). Deterministic: stable union-find +
relabel in sorted source-id order.
"""

import re

PROVENANCE_VERSION = "0.1.0-m3"
_BYLINE_PREFIX = re.compile(r"^\s*by\s+", re.I)
_WS = re.compile(r"\s+")


def _norm_byline(b):
    if not b:
        return None
    b = _BYLINE_PREFIX.sub("", str(b))
    b = _WS.sub(" ", b).strip().lower()
    return b or None


def _norm_wire(w):
    return (str(w).strip().lower() or None) if w else None


def provenance_refine(clusters, sources):
    """`clusters`: source_id → cluster_id (from dedup/semantic). Returns
    (new_clusters, info). Merges sources that share a wire or a byline (and records
    why). Independence only tightens."""
    by_id = {s.get("id"): s for s in sources if s.get("id")}
    ids = sorted(by_id)
    parent = {i: i for i in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    # preserve existing (lexical/semantic) clusters
    by_prev = {}
    for sid, c in clusters.items():
        if sid in parent:
            by_prev.setdefault(c, []).append(sid)
    for grp in by_prev.values():
        for s in grp[1:]:
            union(grp[0], s)

    # group by provenance key
    merges = []
    for key_fn, kind in ((lambda s: _norm_wire(s.get("wire")), "wire"),
                         (lambda s: _norm_byline(s.get("byline")), "byline")):
        buckets = {}
        for sid in ids:
            k = key_fn(by_id[sid])
            if k:
                buckets.setdefault(k, []).append(sid)
        for k, grp in buckets.items():
            for s in grp[1:]:
                if find(grp[0]) != find(s):
                    merges.append({"a": grp[0], "b": s, "signal": kind, "key": k})
                union(grp[0], s)

    roots = sorted({find(i) for i in ids})
    label = {r: f"cl_{k:04d}" for k, r in enumerate(roots)}
    new = {i: label[find(i)] for i in ids}
    info = {"backend": "provenance", "version": PROVENANCE_VERSION,
            "clusters_before": len(set(clusters.values())),
            "clusters_after": len(roots), "provenance_merges": merges}
    return new, info


def main():
    import argparse, json, os
    p = argparse.ArgumentParser(description="받침 provenance independence refine (M3, FR-I1)")
    p.add_argument("--session", required=True)
    args = p.parse_args()
    art = os.path.join(args.session, "artifacts")
    sources = []
    with open(os.path.join(args.session, "sources", "sources.jsonl"), encoding="utf-8") as f:
        for line in f:
            if line.strip():
                sources.append(json.loads(line))
    part = json.load(open(os.path.join(art, "independence_partition.json"), encoding="utf-8"))
    new, info = provenance_refine(part.get("clusters", {}), sources)
    part["clusters"] = new
    part["provenance"] = info
    tmp = os.path.join(art, "independence_partition.json") + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(part, f, ensure_ascii=False, indent=2)
    os.replace(tmp, os.path.join(art, "independence_partition.json"))
    print(f"provenance: {info['clusters_before']} -> {info['clusters_after']} clusters "
          f"({len(info['provenance_merges'])} provenance merges)")


if __name__ == "__main__":
    main()
