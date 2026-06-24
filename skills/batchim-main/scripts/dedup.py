#!/usr/bin/env python3
"""
dedup.py — 받침 independence partition (PRD §6.2 FR-I0). Closes Gap B.

Pure, deterministic, NO LLM / NO network. Collapses near-duplicate / syndicated
sources so "≥2 independent sources" means genuinely independent, not just two
domains. Emits a frozen `independence_partition.json` (source_id -> cluster_id),
deterministic given a fixed source set (stable tiebreak by source_id).

M1 signals: canonical-URL equality + normalized-text simhash Hamming distance.
M3 (FR-I1) adds semantic near-dup and provenance (wire/byline) — TODO.
"""

import argparse
import json
import os
import re
from urllib.parse import urlsplit, parse_qsl, urlunsplit, urlencode

_TRACK = re.compile(r"^(utm_|fbclid|gclid|mc_|ref|ref_src|cmpid|igshid)", re.I)
_WORD = re.compile(r"\w+", re.UNICODE)
SIMHASH_BITS = 64
HAMMING_THRESHOLD = 3  # <=3 bits differ => near-duplicate


def canonical_url(url: str) -> str:
    if not url:
        return ""
    s = urlsplit(url.strip().lower())
    host = s.netloc[4:] if s.netloc.startswith("www.") else s.netloc
    path = s.path.rstrip("/") or "/"
    q = urlencode(sorted((k, v) for k, v in parse_qsl(s.query) if not _TRACK.match(k)))
    return urlunsplit(("https", host, path, q, ""))


def _hash64(token: str) -> int:
    # deterministic FNV-1a 64-bit (reproducible across runs, unlike hash())
    h = 0xcbf29ce484222325
    for b in token.encode("utf-8"):
        h ^= b
        h = (h * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return h


def simhash(text: str) -> int:
    tokens = _WORD.findall((text or "").lower())
    if not tokens:
        return 0
    v = [0] * SIMHASH_BITS
    for tok in tokens:
        hb = _hash64(tok)
        for i in range(SIMHASH_BITS):
            v[i] += 1 if (hb >> i) & 1 else -1
    out = 0
    for i in range(SIMHASH_BITS):
        if v[i] > 0:
            out |= (1 << i)
    return out


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def partition(sources: list) -> dict:
    """sources: [{id, url, snippet|title}]. Returns source_id -> cluster_id.
    Deterministic: process in sorted(source_id) order; a source joins the first
    existing cluster it is near (canonical-URL equal OR simhash within threshold)."""
    ordered = sorted(sources, key=lambda s: s.get("id", ""))
    reps = []  # (cluster_id, canon_url, simhash)
    assign = {}
    for s in ordered:
        sid = s.get("id")
        cu = canonical_url(s.get("url", ""))
        sh = simhash(s.get("snippet") or s.get("title") or "")
        joined = None
        for cid, rcu, rsh in reps:
            if (cu and cu == rcu) or _hamming(sh, rsh) <= HAMMING_THRESHOLD:
                joined = cid
                break
        if joined is None:
            joined = f"cl_{len(reps):04d}"
            reps.append((joined, cu, sh))
        assign[sid] = joined
    return assign


def main():
    p = argparse.ArgumentParser(description="받침 independence partition")
    p.add_argument("--session", required=True)
    p.add_argument("--sources")
    p.add_argument("--out")
    args = p.parse_args()
    src = args.sources or os.path.join(args.session, "sources", "sources.jsonl")
    out = args.out or os.path.join(args.session, "artifacts", "independence_partition.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    rows = []
    with open(src, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    clusters = partition(rows)
    doc = {"source_set_id": None, "dedup_version": "0.1.0-m1",
           "clusters": clusters, "schema_version": 1}
    with open(out, "w", encoding="utf-8") as w:
        json.dump(doc, w, ensure_ascii=False, indent=2)
    print(f"dedup: {len(clusters)} sources -> {len(set(clusters.values()))} clusters -> {out}")


if __name__ == "__main__":
    main()
